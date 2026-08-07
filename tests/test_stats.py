"""Tests for the uncertainty layer.

These are checked against values that can be derived by hand rather than against
whatever the implementation happened to return, because the whole point of this
module is that its output is trusted when a claim gets published.
"""

from __future__ import annotations

import pytest

from agenteval.aggregate import ConditionSummary
from agenteval.stats import (
    compare,
    fisher_exact_2x2,
    mcnemar_exact,
    min_discordant_for_significance,
    paired_bootstrap_delta,
    power_mcnemar,
    required_tasks,
    wilson_interval,
)


# ------------------------------------------------------------------ Wilson
def test_wilson_contains_point_estimate():
    lo, hi = wilson_interval(5, 12)
    assert lo < 5 / 12 < hi


def test_wilson_stays_in_unit_interval_at_extremes():
    # The Wald interval degenerates to zero width here; Wilson must not.
    lo, hi = wilson_interval(0, 12)
    assert lo == 0.0 and 0 < hi < 1

    # At k == n the upper bound is analytically exactly 1; allow float residue.
    lo, hi = wilson_interval(12, 12)
    assert hi == pytest.approx(1.0) and 0 < lo < 1


def test_wilson_narrows_as_n_grows():
    narrow = wilson_interval(50, 100)
    wide = wilson_interval(5, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_wilson_handles_zero_n():
    assert wilson_interval(0, 0) == (0.0, 0.0)


# ----------------------------------------------------------------- McNemar
def test_mcnemar_matches_hand_computed_binomial():
    # b=6, c=0 -> two-sided exact binomial at p=0.5 is 2 * 0.5^6 = 0.03125
    assert mcnemar_exact(6, 0) == pytest.approx(2 * 0.5 ** 6)
    # b=5, c=0 -> 2 * 0.5^5 = 0.0625, just above the 0.05 line
    assert mcnemar_exact(5, 0) == pytest.approx(0.0625)


def test_mcnemar_no_discordant_pairs_is_null():
    assert mcnemar_exact(0, 0) == 1.0


def test_mcnemar_is_symmetric():
    assert mcnemar_exact(7, 2) == mcnemar_exact(2, 7)


def test_mcnemar_balanced_disagreement_is_null():
    assert mcnemar_exact(4, 4) == 1.0


def test_significance_floor_is_six_flips():
    """A structural limit worth pinning: below six one-directional flips, exact
    McNemar cannot return p<0.05 regardless of how many tasks were run."""
    floor = min_discordant_for_significance()
    assert floor == 6
    assert mcnemar_exact(floor, 0) < 0.05
    assert mcnemar_exact(floor - 1, 0) > 0.05


# ------------------------------------------------------------------ Fisher
def test_fisher_symmetric_table_is_null():
    assert fisher_exact_2x2(5, 5, 5, 5) == 1.0


def test_fisher_detects_a_clean_separation():
    assert fisher_exact_2x2(10, 0, 0, 10) < 0.01


# --------------------------------------------------------------- bootstrap
def test_bootstrap_is_deterministic_for_a_given_seed():
    base = {f"t{i}": i % 2 == 0 for i in range(20)}
    cond = {f"t{i}": False for i in range(20)}
    assert paired_bootstrap_delta(base, cond, seed=1) == paired_bootstrap_delta(base, cond, seed=1)


def test_bootstrap_interval_brackets_the_observed_delta():
    base = {f"t{i}": True for i in range(20)}
    cond = {f"t{i}": i < 10 for i in range(20)}   # condition breaks half the tasks
    lo, hi = paired_bootstrap_delta(base, cond, seed=0)
    assert lo <= -0.5 <= hi


def test_bootstrap_on_disjoint_task_sets():
    assert paired_bootstrap_delta({"a": True}, {"b": True}) == (0.0, 0.0)


# ---------------------------------------------------------------- compare
def test_compare_identifies_gained_and_lost_tasks():
    base = {"a": True, "b": True, "c": False, "d": False}
    cond = {"a": True, "b": False, "c": True, "d": False}
    c = compare(base, cond)
    assert c.lost == ["b"]
    assert c.gained == ["c"]
    assert c.n_discordant == 2
    assert c.delta == 0.0            # one broke, one fixed
    assert c.p_value == 1.0


def test_compare_large_one_sided_effect_is_significant():
    base = {f"t{i}": True for i in range(12)}
    cond = {f"t{i}": i >= 8 for i in range(12)}   # 8 tasks broken, none fixed
    c = compare(base, cond)
    assert c.delta == pytest.approx(-8 / 12)
    assert c.significant
    assert c.p_value < 0.05


def test_compare_uses_only_shared_tasks():
    """A partial run should degrade to a smaller honest comparison, not a wrong one."""
    base = {"a": True, "b": True, "c": True}
    cond = {"a": False}
    c = compare(base, cond)
    assert c.n_tasks == 1
    assert c.lost == ["a"]


def test_compare_on_identical_outcomes_is_null():
    same = {f"t{i}": i % 3 == 0 for i in range(15)}
    c = compare(same, dict(same))
    assert c.delta == 0.0
    assert c.p_value == 1.0
    assert not c.significant


# ------------------------------------------------------------------- power
def test_power_rises_with_task_count():
    assert power_mcnemar(12, 0.33) < power_mcnemar(30, 0.33)


def test_twelve_tasks_are_underpowered_for_a_large_effect():
    """The finding that motivated expanding the benchmark."""
    assert power_mcnemar(12, 0.33) < 0.5


def test_required_tasks_reaches_target_power():
    n = required_tasks(0.33, target_power=0.8)
    assert n is not None
    assert power_mcnemar(n, 0.33) >= 0.8


def test_required_tasks_gives_up_on_vanishing_effects():
    assert required_tasks(0.001, target_power=0.8, max_n=50) is None


# ------------------------------------------------------- seed aggregation
def _summary(per_task: dict[str, list[bool]]) -> ConditionSummary:
    cs = ConditionSummary(model="m", condition="c")
    cs.per_task = per_task
    cs.seeds = [0, 1, 2]
    return cs


def test_majority_vote_labels_tasks():
    cs = _summary({
        "solid": [True, True, True],
        "mostly": [True, True, False],
        "flaky": [True, False, False],
        "never": [False, False, False],
    })
    assert cs.task_labels == {"solid": True, "mostly": True, "flaky": False, "never": False}
    assert cs.num_resolved == 2
    assert cs.solve_rate == 0.5


def test_even_seed_ties_resolve_to_unsolved():
    """A 50/50 split is not evidence the task is solved."""
    cs = ConditionSummary(model="m", condition="c")
    cs.per_task = {"tied": [True, False]}
    assert cs.task_labels == {"tied": False}


def test_unstable_tasks_flag_seed_disagreement():
    cs = _summary({"stable": [True, True, True], "unstable": [True, False, True]})
    assert cs.unstable_tasks == ["unstable"]


def test_rollout_rate_differs_from_task_rate():
    """Rollout-level counting is diagnostic only; it must not be mistaken for the
    task-level rate that inference runs on."""
    cs = _summary({"a": [True, True, False], "b": [False, False, False]})
    assert cs.solve_rate == 0.5              # a solved in a majority of seeds
    assert cs.rollout_rate == pytest.approx(2 / 6)
    assert cs.num_rollouts == 6
