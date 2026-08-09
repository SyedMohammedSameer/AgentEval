"""The experiment: show an agent one analyser, measure the ones it never sees.

Each task produces one baseline solution and then two *independent* repair arms
branching from that same baseline:

    baseline  ->  B1: two rounds shown pylint findings
              ->  B2: two rounds shown ruff findings

Branching rather than chaining matters. If B2 continued from B1's output it would
measure the effect of pylint-repair-then-ruff-repair, and the two arms could not be
compared against a common origin. Sharing the baseline makes every comparison
paired within a task, which is where the statistical power comes from at this
sample size.

Both arms record findings from **all three** analysers at every step, not merely
the one being shown. The measurement of interest is precisely what happens to the
tools the agent cannot see.

Arm sizes differ by design, from measured density on this corpus: pylint fires on
100% of files at 4.3 findings each, so B1 runs on every task, while ruff fires on
42% at 0.6 each, so B2 runs only where there is something to fix. Running B2 on a
file with no ruff findings would ask an agent to repair nothing and score the
result as a perfect fix.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .analysers import RUFF_SELECT, analyse_all, suppressions_added
from .harness import (
    ExecResult,
    Task,
    extract_code,
    generation_prompt,
    repair_prompt,
    run_tests,
    write_source,
)

REPAIR_ROUNDS = 2


@dataclass
class Step:
    """One observation: the state of a solution at a point in the loop."""

    task_id: str
    model: str
    arm: str                 # "baseline" | "shown_pylint" | "shown_ruff"
    round: int               # 0 = baseline, then 1..REPAIR_ROUNDS
    shown_tool: str = ""     # which analyser the agent was given, "" at baseline
    tests_passed: bool = False
    test_detail: str = ""
    n_findings: dict = field(default_factory=dict)      # tool -> count
    findings: dict = field(default_factory=dict)        # tool -> [[code, line], ...]
    suppressions_added: dict = field(default_factory=dict)
    completion_tokens: int = 0
    source_chars: int = 0
    error: str = ""


def _measure(task: Task, source: str, prev_source: str | None) -> dict:
    path = write_source(source)
    results = analyse_all(path)
    exec_result: ExecResult = run_tests(task, source)
    return {
        "tests_passed": exec_result.passed,
        "test_detail": exec_result.detail,
        "n_findings": {t: len(r) for t, r in results.items()},
        "findings": {t: [[f.code, f.line] for f in r.findings] for t, r in results.items()},
        "suppressions_added": (suppressions_added(prev_source, source)
                               if prev_source is not None else {}),
        "source_chars": len(source),
        "_raw": results,
    }


def run_task(task: Task, chat, model_name: str) -> list[Step]:
    """Run one task through the baseline and both repair arms.

    `chat` takes a prompt string and returns (reply_text, completion_tokens), so
    the whole experiment is testable against a stub with no GPU involved.
    """
    steps: list[Step] = []

    # --- baseline -----------------------------------------------------------
    try:
        reply, tokens = chat(generation_prompt(task))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step(task.task_id, model_name, "baseline", 0,
                          error=f"{type(exc).__name__}: {exc}"))
        return steps

    base_source = extract_code(reply)
    base = _measure(task, base_source, None)
    raw = base.pop("_raw")
    steps.append(Step(task.task_id, model_name, "baseline", 0,
                      completion_tokens=tokens, **base))

    # --- repair arms, both branching from the baseline -----------------------
    for arm, tool in (("shown_pylint", "pylint"), ("shown_ruff", "ruff")):
        findings = raw[tool].findings
        if not findings:
            # Nothing to repair. Skipping keeps the arm's denominator honest:
            # a file with no findings cannot demonstrate a fix or a suppression.
            continue

        source, prev = base_source, base_source
        current = findings
        for rnd in range(1, REPAIR_ROUNDS + 1):
            try:
                reply, tokens = chat(repair_prompt(source, current, tool))
            except Exception as exc:  # noqa: BLE001
                steps.append(Step(task.task_id, model_name, arm, rnd, shown_tool=tool,
                                  error=f"{type(exc).__name__}: {exc}"))
                break

            new_source = extract_code(reply)
            if not new_source.strip():
                steps.append(Step(task.task_id, model_name, arm, rnd, shown_tool=tool,
                                  error="empty_reply"))
                break

            m = _measure(task, new_source, prev)
            m_raw = m.pop("_raw")
            steps.append(Step(task.task_id, model_name, arm, rnd, shown_tool=tool,
                              completion_tokens=tokens, **m))

            prev, source = new_source, new_source
            current = m_raw[tool].findings
            if not current:
                break   # nothing left that the shown tool can see

    return steps


# --------------------------------------------------------------------- runner


def _completed_keys(path: str) -> set:
    """(task_id, model) pairs already on disk, so a resumed run extends rather
    than repeats. Combined with a fixed shuffle, that makes any partial run a
    uniform random sample and any later run a larger one."""
    done = set()
    if not os.path.exists(path):
        return done
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("arm") == "baseline":
                done.add((r["task_id"], r["model"]))
    return done


def run_study(tasks, chat, model_name, out_path, *, workers=16,
              time_budget_s=None, progress_every=25, abort_after=10):
    """Process tasks until they run out or the time budget expires.

    The budget is a hard stop rather than an estimate. Sizing a run by predicted
    token counts has been wrong before; sizing it by wall clock cannot be. Because
    the task order is a fixed shuffle, stopping early yields a random subset
    rather than a biased prefix, so a short run is a smaller valid study and not a
    broken one.
    """
    done = _completed_keys(out_path)
    todo = [t for t in tasks if (t.task_id, model_name) not in done]
    mine = sum(1 for _, m in done if m == model_name)
    print(f"{model_name}: {len(todo)} tasks to run, {mine} already on disk "
          f"({len(done)} across all models)")

    lock = threading.Lock()
    start = time.time()
    counters = {"tasks": 0, "steps": 0, "stopped": False, "errors": 0,
                "failed_tasks": 0, "last_error": "", "abort_reason": ""}

    def worker(task):
        if counters["stopped"]:
            return
        if time_budget_s and time.time() - start > time_budget_s:
            with lock:
                counters["stopped"] = True
            return
        try:
            steps = run_task(task, chat, model_name)
        except Exception as exc:  # noqa: BLE001 - one task must not sink the run
            steps = [Step(task.task_id, model_name, "baseline", 0,
                          error=f"{type(exc).__name__}: {exc}")]
        with lock:
            with open(out_path, "a") as fh:
                for s in steps:
                    fh.write(json.dumps(asdict(s)) + "\n")
            counters["tasks"] += 1
            counters["steps"] += len(steps)
            counters["errors"] += sum(1 for s in steps if s.error)

            # A task whose baseline errored produced no observation at all. If
            # every one of the first `abort_after` tasks is in that state, the
            # server is up but unusable and the remaining tasks will fail the
            # same way, so stop and surface the error instead of grinding through
            # the whole corpus recording nothing. Doing exactly that, silently,
            # is what made the last run worthless.
            dead = next((s for s in steps if s.arm == "baseline" and s.error), None)
            if dead:
                counters["failed_tasks"] += 1
                counters["last_error"] = dead.error
                if (abort_after and counters["tasks"] >= abort_after
                        and counters["failed_tasks"] == counters["tasks"]):
                    counters["stopped"] = True
                    counters["abort_reason"] = (
                        f"first {counters['tasks']} tasks all failed at the "
                        f"baseline: {dead.error}")

            if counters["tasks"] % progress_every == 0:
                mins = (time.time() - start) / 60
                print(f"  {counters['tasks']} tasks, {counters['steps']} steps, "
                      f"{mins:.1f} min", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(worker, todo))

    mins = (time.time() - start) / 60
    print(f"{model_name}: {counters['tasks']} tasks, {counters['steps']} steps, "
          f"{counters['errors']} errored, {mins:.1f} min")
    if counters["abort_reason"]:
        print(f"  ABORTED: {counters['abort_reason']}")
    elif counters["last_error"]:
        print(f"  {counters['failed_tasks']} tasks failed at baseline, "
              f"last error: {counters['last_error']}")
    return counters
