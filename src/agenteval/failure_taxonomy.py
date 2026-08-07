"""Classify a completed trajectory into a single failure mode.

The taxonomy turns raw pass/fail into *actionable* signal: it separates "the model
never localized the bug" from "the model wrote a patch that didn't apply" from "the
fix was wrong" — each implies a different intervention (context, formatting, reasoning).
This is the analysis the harness exists to produce.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

from .trajectory import ActionType, Trajectory


class FailureMode(str, Enum):
    SOLVED = "solved"                          # resolved — not a failure
    NO_EDIT = "no_edit"                        # never produced any file change
    PATCH_APPLY_FAILED = "patch_apply_failed"  # produced a diff that won't apply
    WRONG_FIX = "wrong_fix"                     # patch applied but hidden tests still fail
    MAX_STEPS = "max_steps"                     # ran out of budget while still progressing
    LIVELOCK = "livelock"                       # burned the budget repeating itself
    EVAL_TIMEOUT = "eval_timeout"              # candidate patch hangs the test suite
    PROTOCOL_VIOLATION = "protocol_violation"   # model couldn't follow the action format
    UNKNOWN = "unknown"


# Share of steps that must be repeats of an earlier action before exhausting the
# budget is read as looping rather than as running out of room.
LIVELOCK_REPETITION = 0.5


# A short, human-facing gloss per mode — surfaced in the dashboard.
DESCRIPTIONS = {
    FailureMode.SOLVED: "Patch applied and all target tests passed.",
    FailureMode.NO_EDIT: "Agent submitted or gave up without editing any file (localization/confidence failure).",
    FailureMode.PATCH_APPLY_FAILED: "Agent's diff was malformed and did not apply (edit-formatting failure).",
    FailureMode.WRONG_FIX: "Patch applied cleanly but did not fix the bug (reasoning/correctness failure).",
    FailureMode.MAX_STEPS: "Ran out of step budget while still taking new actions (efficiency failure — a bigger budget may help).",
    FailureMode.LIVELOCK: "Spent the budget repeating actions it had already taken (non-termination — a bigger budget will not help).",
    FailureMode.EVAL_TIMEOUT: "Candidate patch caused the test suite to time out (introduced a hang/regression).",
    FailureMode.PROTOCOL_VIOLATION: "Model repeatedly failed to emit a valid action (instruction-following failure).",
    FailureMode.UNKNOWN: "Unclassified.",
}


def repetition_ratio(traj: Trajectory) -> float:
    """Share of steps that repeated an action the agent had already taken.

    0.0 means every step was distinct; values near 1.0 mean the agent cycled over
    a handful of actions. Computed over (action_type, action_input) pairs, so
    re-running the same command counts as a repeat while a different command of
    the same kind does not.
    """
    if not traj.steps:
        return 0.0
    signatures = [(s.action_type, s.action_input) for s in traj.steps]
    return 1.0 - len(set(signatures)) / len(signatures)


def classify(traj: Trajectory) -> FailureMode:
    if traj.resolved:
        return FailureMode.SOLVED

    reason = (traj.eval_details or {}).get("reason", "")

    # Instruction-following: if a large share of steps produced no valid action.
    action_counts = Counter(s.action_type for s in traj.steps)
    n = max(traj.num_steps, 1)
    if action_counts.get(ActionType.NONE.value, 0) / n >= 0.5:
        return FailureMode.PROTOCOL_VIOLATION

    # Non-termination outranks the outcome labels below. A run that spent its
    # whole budget cycling never reached a decision, so calling it `no_edit`
    # ("gave up without editing") or `wrong_fix` ("answered incorrectly") reads
    # an intent into it that was never formed. The distinction is load-bearing:
    # raising max_steps from 20 to 30 on a 1.5B converted zero of 16 such runs
    # while costing 44% more tokens, whereas a genuine budget shortfall is
    # exactly the case a larger budget does fix.
    if traj.stop_reason == "max_steps" and repetition_ratio(traj) >= LIVELOCK_REPETITION:
        return FailureMode.LIVELOCK

    if not traj.patch.strip():
        return FailureMode.NO_EDIT
    if reason == "patch_apply_failed":
        return FailureMode.PATCH_APPLY_FAILED
    if reason == "eval_timeout":
        return FailureMode.EVAL_TIMEOUT
    if reason in ("tests_failed", "test_regression"):
        # Distinguish "gave up" from "wrong answer" using the stop reason.
        if traj.stop_reason == "max_steps":
            return FailureMode.MAX_STEPS
        return FailureMode.WRONG_FIX
    if traj.stop_reason == "max_steps":
        return FailureMode.MAX_STEPS
    return FailureMode.UNKNOWN


def annotate(traj: Trajectory) -> Trajectory:
    traj.failure_mode = classify(traj).value
    return traj
