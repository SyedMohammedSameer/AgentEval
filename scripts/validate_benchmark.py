"""Sanity-check the local benchmark.

Three properties, each of which has a distinct failure mode if it goes unchecked:

  1. **The bug is real.** The buggy workspace must FAIL its hidden oracle. Without
     this a task is free points for every condition.

  2. **The task is solvable.** Applying the stored gold patch must make the oracle
     PASS. This is the check that matters most: an impossible or self-contradictory
     task scores zero under every condition forever, which does not look like a
     broken task in the results — it looks like a hard one, and it silently drags
     every measured effect toward zero.

  3. **The visible tests carry signal.** The basic test must fail on the buggy code,
     otherwise `run_tests` tells the agent nothing and the tool-availability ablation
     is measuring a tool with nothing to report.

Run: python scripts/validate_benchmark.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "local"


TIMEOUT_S = 60


def _run_pytest(workdir: Path, cmd: str, timeout: int = TIMEOUT_S):
    """Run the suite, returning None if it hung.

    A hang is a benchmark defect in its own right — buggy code that loops forever
    turns every rollout on that task into an `eval_timeout` — so it is reported as
    a validation problem rather than being allowed to abort the whole sweep.
    """
    # Same environment the real evaluator uses, so validation and scoring agree on
    # which interpreter `python -m pytest` resolves to.
    from agenteval.environments.local import sandbox_env

    try:
        return subprocess.run(
            cmd, shell=True, cwd=workdir, capture_output=True, text=True,
            timeout=timeout, env=sandbox_env(),
        )
    except subprocess.TimeoutExpired:
        return None


def _stage(task_dir: Path, tmp: Path, *, with_oracle: bool, with_fix: bool) -> None:
    shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True)
    if with_fix and (task_dir / "solution").exists():
        shutil.copytree(task_dir / "solution", tmp, dirs_exist_ok=True)
    if with_oracle:
        shutil.copytree(task_dir / "tests", tmp, dirs_exist_ok=True)


def check(task_dir: Path) -> tuple[bool, list[str]]:
    import yaml

    spec = yaml.safe_load((task_dir / "task.yaml").read_text())
    eval_cmd = spec.get("eval_test_cmd", "python -m pytest -q")
    dev_cmd = spec.get("dev_test_cmd", "python -m pytest -q test_basic.py")
    problems: list[str] = []

    def run_staged(*, with_oracle: bool, with_fix: bool):
        tmp = Path(tempfile.mkdtemp())
        try:
            _stage(task_dir, tmp, with_oracle=with_oracle, with_fix=with_fix)
            return _run_pytest(tmp, eval_cmd if with_oracle else dev_cmd)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # 1. buggy code must fail the oracle
    res = run_staged(with_oracle=True, with_fix=False)
    if res is None:
        problems.append(f"oracle HUNG on buggy code (>{TIMEOUT_S}s) — every rollout would time out")
    elif res.returncode == 0:
        problems.append("buggy workspace PASSES the oracle (bug is not real)")

    has_gold = (task_dir / "solution").exists()
    if not has_gold:
        problems.append("no gold patch — solvability unverified")
    else:
        # 2. gold patch must pass the oracle
        res = run_staged(with_oracle=True, with_fix=True)
        if res is None:
            problems.append(f"oracle HUNG with the gold patch (>{TIMEOUT_S}s)")
        elif res.returncode != 0:
            tail = (res.stdout + res.stderr).strip().splitlines()[-3:]
            problems.append("gold patch FAILS the oracle (task unsolvable): " + " / ".join(tail))

    # 3. visible tests must detect the bug
    res = run_staged(with_oracle=False, with_fix=False)
    if res is None:
        problems.append(f"basic tests HUNG on buggy code (>{TIMEOUT_S}s)")
    elif res.returncode == 0:
        problems.append("basic tests PASS on buggy code (run_tests gives the agent no signal)")

    # 3b. and must pass once fixed, or the agent is chasing a broken test
    if has_gold:
        res = run_staged(with_oracle=False, with_fix=True)
        if res is None:
            problems.append(f"basic tests HUNG with the gold patch (>{TIMEOUT_S}s)")
        elif res.returncode != 0:
            tail = (res.stdout + res.stderr).strip().splitlines()[-2:]
            problems.append("basic tests FAIL even with the gold patch: " + " / ".join(tail))

    return not problems, problems


def main() -> None:
    tasks = sorted(p for p in ROOT.iterdir() if (p / "task.yaml").exists())
    if not tasks:
        raise SystemExit(f"no tasks found under {ROOT} — run build_local_benchmark.py first")

    ok = 0
    for t in tasks:
        good, problems = check(t)
        ok += good
        print(f"{'PASS' if good else 'FAIL'}  {t.name:32s} {'' if good else problems[0]}")
        for extra in problems[1:]:
            print(f"{'':38s}{extra}")

    print(f"\n{ok}/{len(tasks)} tasks valid")
    if ok != len(tasks):
        sys.exit(1)


if __name__ == "__main__":
    main()
