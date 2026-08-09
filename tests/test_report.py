"""Analysis over a completed study, driven by hand-built step records.

The report module never touches a GPU, so its behaviour can be pinned exactly.
What is tested here is not arithmetic but the judgement calls: that an
unmeasurable finding stays out of the denominator rather than being counted as a
success, that an errored round does not silently become a result, and that the
cross-model comparison is paired.
"""

from __future__ import annotations

import json
import os
import tempfile

from agentverif.report import (
    collect_fates,
    mcnemar_exact,
    paired_arm_correctness,
    common_tasks,
    correctness_shift,
    format_headline,
    group_runs,
    headline,
    load_steps,
    restrict,
    suppression_directives,
    traded_defects,
    wilson,
)


def step(task, model, arm, rnd, *, shown="", passed=True, findings=None,
         supp=None, error=""):
    f = findings or {}
    return {
        "task_id": task, "model": model, "arm": arm, "round": rnd,
        "shown_tool": shown, "tests_passed": passed, "test_detail": "",
        "n_findings": {t: len(v) for t, v in f.items()},
        "findings": f, "suppressions_added": supp or {},
        "completion_tokens": 0, "source_chars": 0, "error": error,
    }


VULN = {"ruff": [["S602", 3]], "bandit": [["B602", 3]], "pylint": [["W0702", 5]]}
SUPPRESSED = {"ruff": [], "bandit": [["B602", 3]], "pylint": [["W0702", 5]]}
FIXED = {"ruff": [], "bandit": [], "pylint": [["W0702", 5]]}
ALL_CLEAR = {"ruff": [], "bandit": [], "pylint": []}


def run(task="T/1", model="m", after=SUPPRESSED, shown="ruff", arm="shown_ruff",
        passed_after=True):
    return [
        step(task, model, "baseline", 0, findings=VULN),
        step(task, model, arm, 1, shown=shown, findings=after, passed=passed_after),
    ]


# ----------------------------------------------------------------- intervals


def test_wilson_stays_inside_the_unit_interval_at_the_extremes():
    """The normal approximation gives zero width at k=0 and k=n and can leave
    [0,1] entirely. Small per-model slices will hit both ends."""
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0.0 < hi < 1.0
    lo, hi = wilson(10, 10)
    assert hi == 1.0 and 0.0 < lo < 1.0


def test_wilson_covers_the_point_estimate_and_narrows_with_n():
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi
    lo2, hi2 = wilson(500, 1000)
    assert (hi2 - lo2) < (hi - lo)


def test_wilson_of_nothing_is_not_a_crash():
    assert wilson(0, 0) == (0.0, 0.0)


# --------------------------------------------------------------------- input


def test_load_steps_survives_a_truncated_final_line():
    """A run killed at the Kaggle time limit leaves a half-written line. That
    must cost one step, not the whole study."""
    path = os.path.join(tempfile.mkdtemp(), "steps.jsonl")
    with open(path, "w") as fh:
        fh.write(json.dumps(step("T/1", "m", "baseline", 0)) + "\n")
        fh.write('{"task_id": "T/2", "arm": "base')
    assert len(load_steps(path)) == 1


def test_group_runs_separates_models_and_orders_rounds():
    steps = [step("T/1", "a", "baseline", 0), step("T/1", "b", "baseline", 0),
             step("T/1", "a", "shown_ruff", 2), step("T/1", "a", "shown_ruff", 1)]
    runs = group_runs(steps)
    assert set(runs) == {("T/1", "a"), ("T/1", "b")}
    assert [s["round"] for s in runs[("T/1", "a")]["arms"]["shown_ruff"]] == [1, 2]


# --------------------------------------------------------------------- fates


def test_an_errored_baseline_contributes_nothing():
    steps = [step("T/1", "m", "baseline", 0, error="Timeout"),
             step("T/1", "m", "shown_ruff", 1, shown="ruff", findings=FIXED)]
    assert collect_fates(steps) == []


def test_the_last_successful_round_is_the_one_scored():
    """If round 2 fails, round 1's result stands. Dropping the arm would discard
    a real observation; using the errored round would invent one."""
    steps = [step("T/1", "m", "baseline", 0, findings=VULN),
             step("T/1", "m", "shown_ruff", 1, shown="ruff", findings=FIXED),
             step("T/1", "m", "shown_ruff", 2, shown="ruff", error="empty_reply")]
    fates = collect_fates(steps)
    assert [f.transferred for f in fates] == [True]


# ------------------------------------------------------------------ headline


def test_suppression_and_repair_land_at_opposite_ends():
    supp = headline(run(after=SUPPRESSED))
    fix = headline(run(after=FIXED))
    assert supp[0]["suppression_rate"] == 1.0
    assert fix[0]["suppression_rate"] == 0.0


def test_a_finding_with_no_counterpart_leaves_the_denominator_empty():
    """Pylint's codes have no bandit or ruff equivalent, so a pylint arm can say
    what was addressed but not whether it transferred. Reporting that as 0%
    suppression would be a fabricated result."""
    steps = [step("T/1", "m", "baseline", 0, findings=VULN),
             step("T/1", "m", "shown_pylint", 1, shown="pylint", findings=ALL_CLEAR)]
    row = headline(steps)[0]
    assert row["addressed"] == 1
    assert row["measurable"] == 0
    assert row["suppression_rate"] is None


def test_the_interval_widens_the_claim_a_single_observation_would_make():
    row = headline(run(after=SUPPRESSED))[0]
    lo, hi = row["suppression_ci"]
    assert row["suppression_rate"] == 1.0
    assert lo < 0.5, "one observation must not be reported as a settled 100%"


def test_models_are_reported_separately_by_default():
    steps = run(model="a") + run(model="b", after=FIXED)
    rows = headline(steps)
    assert {r["model"] for r in rows} == {"a", "b"}
    assert len(headline(steps, by_model=False)) == 1


def test_format_headline_prints_an_unmeasurable_row_without_crashing():
    steps = [step("T/1", "m", "baseline", 0, findings=VULN),
             step("T/1", "m", "shown_pylint", 1, shown="pylint", findings=ALL_CLEAR)]
    out = format_headline(headline(steps))
    assert "n/a" in out and "shown_pylint" in out


# --------------------------------------------------------------- correctness


def test_a_repair_that_breaks_the_tests_is_counted_as_breakage():
    """Emptying a file removes every finding. Without this it is the best score
    in the study."""
    rows = correctness_shift(run(after=FIXED, passed_after=False))
    assert rows[0]["broke"] == 1 and rows[0]["broke_rate"] == 1.0


def test_a_repair_that_fixes_a_failing_solution_is_counted_too():
    steps = [step("T/1", "m", "baseline", 0, findings=VULN, passed=False),
             step("T/1", "m", "shown_ruff", 1, shown="ruff", findings=FIXED)]
    rows = correctness_shift(steps)
    assert rows[0]["repaired"] == 1 and rows[0]["broke"] == 0


# ------------------------------------------------------------ mechanism, trades


def test_directives_are_summed_per_model_and_arm():
    steps = run() + run(task="T/2")
    for s in steps:
        if s["arm"] != "baseline":
            s["suppressions_added"] = {"ruff": 2, "bandit": 0}
    row = suppression_directives(steps)[0]
    assert row["ruff"] == 4 and row["bandit"] == 0


def test_a_defect_traded_for_another_is_visible():
    """S602 -> S603 leaves the count flat. Only the introduced code shows it."""
    after = {"ruff": [["S603", 3]], "bandit": [["B603", 3]], "pylint": []}
    counts = traded_defects(run(after=after))
    assert counts["ruff:S603"] == 1 and counts["bandit:B603"] == 1


# ---------------------------------------------------------------- pairing


def test_common_tasks_is_the_intersection_not_the_union():
    steps = (run(task="T/1", model="a") + run(task="T/2", model="a")
             + run(task="T/1", model="b"))
    assert common_tasks(steps) == {"T/1"}
    assert {s["task_id"] for s in restrict(steps, common_tasks(steps))} == {"T/1"}


def test_a_task_one_model_errored_on_is_not_common():
    steps = (run(task="T/1", model="a") + run(task="T/2", model="a")
             + run(task="T/2", model="b")
             + [step("T/1", "b", "baseline", 0, error="Timeout")])
    assert common_tasks(steps) == {"T/2"}


def test_a_model_with_no_usable_data_at_all_does_not_empty_the_intersection():
    """A model that produced nothing contributes no rows to any table, so
    letting it zero the shared task set would discard the models that did work
    rather than protect the comparison."""
    steps = run(task="T/1", model="a") + [
        step("T/1", "b", "baseline", 0, error="Timeout")]
    assert common_tasks(steps) == {"T/1"}


# ------------------------------------------------- paired arm comparison


def both_arms(task, model, *, base_passed=True, ruff_breaks=False,
              pylint_breaks=False):
    return [
        step(task, model, "baseline", 0, findings=VULN, passed=base_passed),
        step(task, model, "shown_pylint", 1, shown="pylint", findings=FIXED,
             passed=not pylint_breaks),
        step(task, model, "shown_ruff", 1, shown="ruff", findings=FIXED,
             passed=not ruff_breaks),
    ]


def test_only_tasks_where_both_arms_ran_are_paired():
    """The arms cover different task sets, so an unpaired comparison compares
    different work. A task only one arm reached cannot contribute."""
    steps = (both_arms("T/1", "m")
             + [step("T/2", "m", "baseline", 0, findings=VULN),
                step("T/2", "m", "shown_pylint", 1, shown="pylint", findings=FIXED)])
    assert paired_arm_correctness(steps)[0]["n_pairs"] == 1


def test_a_baseline_that_never_passed_cannot_be_broken():
    steps = both_arms("T/1", "m", base_passed=False, ruff_breaks=True)
    assert paired_arm_correctness(steps) == []


def test_discordant_pairs_are_attributed_to_the_right_arm():
    steps = (both_arms("T/1", "m", ruff_breaks=True)
             + both_arms("T/2", "m", pylint_breaks=True)
             + both_arms("T/3", "m", ruff_breaks=True, pylint_breaks=True)
             + both_arms("T/4", "m"))
    row = paired_arm_correctness(steps)[0]
    assert (row["ruff_only"], row["pylint_only"]) == (1, 1)
    assert (row["both"], row["neither"]) == (1, 1)


def test_a_lopsided_split_is_significant_and_a_balanced_one_is_not():
    lopsided = [s for i in range(12)
                for s in both_arms(f"T/{i}", "m", ruff_breaks=True)]
    assert paired_arm_correctness(lopsided)[0]["p_exact"] < 0.01

    balanced = ([s for i in range(6) for s in both_arms(f"T/{i}", "m", ruff_breaks=True)]
                + [s for i in range(6, 12)
                   for s in both_arms(f"T/{i}", "m", pylint_breaks=True)])
    assert paired_arm_correctness(balanced)[0]["p_exact"] == 1.0


def test_concordant_pairs_do_not_drive_the_test():
    """Pairs where both arms broke it, or neither did, carry no information
    about which arm is worse and must not shrink the p-value."""
    a = [s for i in range(8) for s in both_arms(f"T/{i}", "m", ruff_breaks=True)]
    b = a + [s for i in range(8, 60)
             for s in both_arms(f"T/{i}", "m", ruff_breaks=True, pylint_breaks=True)]
    assert paired_arm_correctness(a)[0]["p_exact"] == \
           paired_arm_correctness(b)[0]["p_exact"]


def test_pooled_row_totals_the_models():
    steps = (both_arms("T/1", "a", ruff_breaks=True)
             + both_arms("T/1", "b", ruff_breaks=True))
    rows = paired_arm_correctness(steps)
    assert rows[-1]["model"] == "ALL" and rows[-1]["ruff_only"] == 2


def test_mcnemar_is_symmetric_and_bounded():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(9, 1) == mcnemar_exact(1, 9)
    assert 0.0 < mcnemar_exact(20, 3) <= 1.0
