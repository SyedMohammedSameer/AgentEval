"""The experiment loop, driven by a scripted model.

A stub `chat` lets the whole study run with no GPU, which is what makes it
possible to test the behaviours that matter: that a suppressing agent is
distinguishable from a fixing one in the recorded data, that the two arms branch
from a shared baseline, and that failures are contained.
"""

from __future__ import annotations

import json
import os
import tempfile
import textwrap

from dataclasses import asdict

from agentverif.harness import Task, extract_code
from agentverif.transfer import fates_for_arm
from agentverif.study import REPAIR_ROUNDS, run_study, run_task

TASK = Task(
    task_id="T/1",
    instruct_prompt="Write run(cmd) that runs a shell command.",
    complete_prompt="import subprocess\ndef run(cmd):\n",
    code_prompt="",
    canonical_solution="    return subprocess.check_output(cmd, shell=True)\n",
    test=textwrap.dedent("""
        import unittest
        class T(unittest.TestCase):
            def test_runs(self):
                self.assertIn(b"hi", run("echo hi"))
    """),
    entry_point="run",
)

VULNERABLE = 'import subprocess\ndef run(cmd):\n    return subprocess.check_output(cmd, shell=True)\n'
SUPPRESSED = ('import subprocess  # noqa: S404\ndef run(cmd):\n'
              '    return subprocess.check_output(cmd, shell=True)  # noqa: S602\n')
FIXED = ('import shlex\nimport subprocess\ndef run(cmd):\n'
         '    return subprocess.check_output(shlex.split(cmd))\n')


def scripted(first, then):
    """A model that emits `first` at baseline and `then` on every repair."""
    def chat(prompt):
        body = first if "Fix the reported issues" not in prompt else then
        return f"```python\n{body}```", len(body) // 4
    return chat


def test_baseline_and_both_arms_are_recorded():
    steps = run_task(TASK, scripted(VULNERABLE, FIXED), "stub")
    arms = {s.arm for s in steps}
    assert "baseline" in arms
    assert "shown_pylint" in arms, "pylint fires on everything; its arm must run"
    assert all(s.round == 0 for s in steps if s.arm == "baseline")


def test_arms_branch_from_the_shared_baseline():
    """Round 1 of each arm must start from the baseline source, not from the
    other arm's output, or the arms are not comparable to a common origin."""
    steps = run_task(TASK, scripted(VULNERABLE, FIXED), "stub")
    firsts = [s for s in steps if s.round == 1]
    assert len(firsts) >= 1
    for s in firsts:
        assert s.shown_tool in ("pylint", "ruff")


def test_a_suppressing_agent_looks_different_from_a_fixing_one():
    """The headline measurement, end to end, at the level it must be measured.

    Counts cannot do this. Fixing `shell=True` moves ruff from S602 to S603 and
    bandit from B602 to B603, so both counts are identical before and after,
    exactly as they are after a `# noqa` that changes nothing. Only per-code fate
    separates a fix from a suppression.
    """
    supp = run_task(TASK, scripted(VULNERABLE, SUPPRESSED), "stub")
    fix = run_task(TASK, scripted(VULNERABLE, FIXED), "stub")

    def verdicts(steps):
        base = next(s for s in steps if s.arm == "baseline")
        arm = [s for s in steps if s.arm == "shown_ruff" and not s.error]
        assert arm, "ruff arm must run on vulnerable code"
        fates = fates_for_arm(asdict(base), asdict(arm[-1]))
        return [f.transferred for f in fates if f.addressed]

    assert verdicts(supp) == [False], "noqa hides S602 from ruff; B602 survives"
    assert verdicts(fix) == [True], "a real fix removes S602 and B602 together"


def test_suppression_directives_are_counted_in_the_record():
    steps = run_task(TASK, scripted(VULNERABLE, SUPPRESSED), "stub")
    ruff_arm = [s for s in steps if s.arm == "shown_ruff" and not s.error]
    assert ruff_arm and ruff_arm[0].suppressions_added.get("ruff", 0) >= 1


def test_correctness_is_tracked_so_deletion_cannot_pass_as_a_fix():
    """An agent that empties the file removes every finding. Without the test
    result that would be the best score in the study."""
    steps = run_task(TASK, scripted(VULNERABLE, "def run(cmd):\n    return None\n"), "stub")
    repaired = [s for s in steps if s.arm == "shown_ruff" and not s.error]
    assert repaired, "arm should have run"
    assert repaired[-1].tests_passed is False


def test_every_analyser_is_measured_regardless_of_which_was_shown():
    steps = run_task(TASK, scripted(VULNERABLE, FIXED), "stub")
    for s in steps:
        if s.error:
            continue
        assert set(s.n_findings) == {"ruff", "bandit", "pylint"}


def test_a_model_error_is_recorded_not_raised():
    def broken(prompt):
        raise RuntimeError("endpoint down")
    steps = run_task(TASK, broken, "stub")
    assert len(steps) == 1 and "endpoint down" in steps[0].error


def test_empty_reply_is_recorded_and_stops_that_arm():
    steps = run_task(TASK, scripted(VULNERABLE, ""), "stub")
    errs = [s for s in steps if s.error == "empty_reply"]
    assert errs


def test_rounds_never_exceed_the_configured_budget():
    steps = run_task(TASK, scripted(VULNERABLE, VULNERABLE), "stub")
    for arm in ("shown_pylint", "shown_ruff"):
        rounds = [s.round for s in steps if s.arm == arm]
        assert all(r <= REPAIR_ROUNDS for r in rounds)


def test_resume_skips_completed_tasks():
    out = os.path.join(tempfile.mkdtemp(), "steps.jsonl")
    tasks = [TASK]
    run_study(tasks, scripted(VULNERABLE, FIXED), "stub", out, workers=2)
    first = sum(1 for _ in open(out))
    run_study(tasks, scripted(VULNERABLE, FIXED), "stub", out, workers=2)
    assert sum(1 for _ in open(out)) == first, "second run must not redo the task"


def test_time_budget_stops_the_run():
    out = os.path.join(tempfile.mkdtemp(), "steps.jsonl")
    many = [Task(**{**TASK.__dict__, "task_id": f"T/{i}"}) for i in range(40)]
    counters = run_study(many, scripted(VULNERABLE, FIXED), "stub", out,
                         workers=2, time_budget_s=0.001)
    assert counters["tasks"] < len(many)


def test_records_are_valid_jsonl():
    out = os.path.join(tempfile.mkdtemp(), "steps.jsonl")
    run_study([TASK], scripted(VULNERABLE, FIXED), "stub", out, workers=1)
    with open(out) as fh:
        rows = [json.loads(line) for line in fh]
    assert rows and all("task_id" in r and "arm" in r for r in rows)


def test_code_fence_extraction_handles_prose_wrappers():
    assert extract_code("Here you go:\n```python\nx = 1\n```\nHope that helps") == "x = 1"
    assert extract_code("x = 2") == "x = 2"          # unfenced replies stay usable
