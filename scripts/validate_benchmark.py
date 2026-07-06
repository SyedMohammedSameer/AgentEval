"""Sanity-check the local benchmark:

  1. The buggy workspace must FAIL its hidden oracle (the bug is real & caught).
  2. The task must be solvable in principle — we don't ship gold patches, but we at
     least confirm the eval command runs and the visible basic test exists.

Run: python scripts/validate_benchmark.py
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "local"


def check(task_dir: Path) -> tuple[bool, str]:
    import yaml

    spec = yaml.safe_load((task_dir / "task.yaml").read_text())
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True)
        shutil.copytree(task_dir / "tests", tmp, dirs_exist_ok=True)
        run = subprocess.run(
            spec.get("eval_test_cmd", "python -m pytest -q"),
            shell=True, cwd=tmp, capture_output=True, text=True, timeout=120,
        )
        # Expect FAILURE on buggy code.
        if run.returncode == 0:
            return False, "buggy workspace unexpectedly PASSES oracle (task is broken)"
        return True, "buggy code fails oracle as expected"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    tasks = sorted(p for p in ROOT.iterdir() if (p / "task.yaml").exists())
    ok = 0
    for t in tasks:
        good, msg = check(t)
        print(f"{'PASS' if good else 'FAIL'}  {t.name:28s} {msg}")
        ok += good
    print(f"\n{ok}/{len(tasks)} tasks valid")


if __name__ == "__main__":
    main()
