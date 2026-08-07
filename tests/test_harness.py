"""Unit tests for the harness internals (no model calls, fast)."""

from __future__ import annotations

from agenteval.failure_taxonomy import FailureMode, classify
from agenteval.tools import parse_action
from agenteval.trajectory import ActionType, Step, Trajectory


# ------------------------------------------------------------------ parsing
def test_parse_bash():
    a = parse_action("Let me look.\n<bash>cat foo.py</bash>")
    assert a.type == ActionType.BASH
    assert a.input == "cat foo.py"
    assert "look" in a.thought


def test_earliest_tag_wins():
    # A bash command appears first; a later stray run_tests mention must NOT hijack it.
    text = "First I'll <bash>ls</bash> and then maybe <run_tests></run_tests>"
    a = parse_action(text)
    assert a.type == ActionType.BASH
    assert a.input == "ls"


def test_parse_submit():
    a = parse_action("Done.\n<submit></submit>")
    assert a.type == ActionType.SUBMIT


def test_no_action():
    a = parse_action("I am just thinking out loud.")
    assert a.type == ActionType.NONE


# --------------------------------------------------------------- taxonomy
def _traj(**kw) -> Trajectory:
    t = Trajectory(task_id="t", run_name="r", model="m")
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_solved():
    assert classify(_traj(resolved=True)) == FailureMode.SOLVED


def test_no_edit():
    t = _traj(patch="", stop_reason="submit")
    t.add(Step(0, "", ActionType.BASH.value, "ls", "ok"))
    assert classify(t) == FailureMode.NO_EDIT


def test_patch_apply_failed():
    t = _traj(patch="diff --git a b", eval_details={"reason": "patch_apply_failed"})
    t.add(Step(0, "", ActionType.BASH.value, "x", "y"))
    assert classify(t) == FailureMode.PATCH_APPLY_FAILED


def test_wrong_fix_vs_max_steps():
    base = dict(patch="diff --git a b", eval_details={"reason": "tests_failed"})
    t1 = _traj(stop_reason="submit", **base)
    t1.add(Step(0, "", ActionType.BASH.value, "x", "y"))
    assert classify(t1) == FailureMode.WRONG_FIX

    t2 = _traj(stop_reason="max_steps", **base)
    t2.add(Step(0, "", ActionType.BASH.value, "x", "y"))
    assert classify(t2) == FailureMode.MAX_STEPS


def test_protocol_violation():
    t = _traj(patch="", stop_reason="max_steps")
    for i in range(4):
        t.add(Step(i, "", ActionType.NONE.value, "", "no action"))
    assert classify(t) == FailureMode.PROTOCOL_VIOLATION


# --------------------------------------------------- local provider round-trip
def test_local_provider_eval_roundtrip():
    """A correct fix (produced through the real environment) resolves; empty doesn't."""
    from pathlib import Path

    from agenteval.providers.local import LocalProvider

    prov = LocalProvider()
    tasks = {t.task_id: t for t in prov.load_tasks("all")}
    task = tasks["dedup-preserve-order"]

    # Produce a patch exactly the way the agent would: edit the file in a fresh
    # environment, then read back git diff.
    env = prov.make_environment(task)
    fixed = (
        "def dedup(items):\n"
        "    seen = set()\n"
        "    out = []\n"
        "    for x in items:\n"
        "        if x not in seen:\n"
        "            seen.add(x)\n"
        "            out.append(x)\n"
        "    return out\n"
    )
    Path(env.workdir, "seqtools.py").write_text(fixed)
    good_patch = env.get_patch()
    env.teardown()

    assert good_patch.strip(), "expected a non-empty diff"
    assert prov.evaluate(task, good_patch).resolved is True
    assert prov.evaluate(task, "").resolved is False


# ------------------------------------------ budget exhaustion vs livelock
def _steps(traj, actions):
    for i, (kind, payload) in enumerate(actions):
        traj.add(Step(i, "", kind, payload, "obs"))
    return traj


def test_repeated_actions_classify_as_livelock():
    """Raising max_steps converts none of these, so they must not be labelled as
    a budget shortfall — the fix they point at is termination, not more room."""
    from agenteval.failure_taxonomy import repetition_ratio

    t = _traj(patch="", stop_reason="max_steps")
    _steps(t, [(ActionType.BASH.value, "cat foo.py")] * 10)
    assert repetition_ratio(t) > 0.5
    assert classify(t) == FailureMode.LIVELOCK


def test_livelock_outranks_no_edit():
    """Looping for the whole budget without editing is not the same failure as
    submitting an empty patch after two steps; only the latter is a decision."""
    looped = _traj(patch="", stop_reason="max_steps")
    _steps(looped, [(ActionType.BASH.value, "ls")] * 12)
    assert classify(looped) == FailureMode.LIVELOCK

    gave_up = _traj(patch="", stop_reason="submit")
    _steps(gave_up, [(ActionType.BASH.value, "ls"), (ActionType.SUBMIT.value, "")])
    assert classify(gave_up) == FailureMode.NO_EDIT


def test_distinct_actions_remain_max_steps():
    t = _traj(patch="diff --git a b", eval_details={"reason": "tests_failed"},
              stop_reason="max_steps")
    _steps(t, [(ActionType.BASH.value, f"cmd {i}") for i in range(10)])
    assert classify(t) == FailureMode.MAX_STEPS


def test_partial_repetition_below_threshold_is_max_steps():
    t = _traj(patch="diff --git a b", eval_details={"reason": "tests_failed"},
              stop_reason="max_steps")
    # 7 distinct of 10 steps -> ratio 0.3, under the livelock threshold.
    _steps(t, [(ActionType.BASH.value, f"cmd {i}") for i in range(7)]
              + [(ActionType.BASH.value, "cmd 0")] * 3)
    assert classify(t) == FailureMode.MAX_STEPS


def test_livelock_detected_even_with_a_patch_present():
    """An agent that edited, then looped, is still non-terminating."""
    t = _traj(patch="diff --git a b", eval_details={"reason": "tests_failed"},
              stop_reason="max_steps")
    _steps(t, [(ActionType.RUN_TESTS.value, "")] * 8)
    assert classify(t) == FailureMode.LIVELOCK


def test_repetition_ratio_on_empty_trajectory():
    from agenteval.failure_taxonomy import repetition_ratio

    assert repetition_ratio(_traj()) == 0.0
