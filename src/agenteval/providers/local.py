"""Synthetic local benchmark — real bugs, hidden pytest oracle, zero Docker.

On-disk layout of each task:

    benchmarks/local/<task_id>/
        task.yaml        # {id, problem_statement, dev_test_cmd?, eval_test_cmd, timeout?}
        workspace/       # the buggy code the agent is given and edits
        tests/           # hidden oracle tests, injected only at evaluation time

Evaluation is hermetic: we take a *fresh* copy of workspace/, apply the agent's patch,
drop the hidden tests in, and run the eval command. resolved := tests exit 0.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from ..environments.local import LocalEnvironment, sandbox_env
from .base import EvalResult, Task

BENCH_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "local"


class LocalProvider:
    name = "local"

    def _task_dir(self, task_id: str) -> Path:
        return BENCH_ROOT / task_id

    def load_tasks(self, subset: str) -> list[Task]:
        # subset "smoke"/"all" => every task dir; or a comma-separated list of ids.
        if subset in ("smoke", "all", ""):
            ids = sorted(p.name for p in BENCH_ROOT.iterdir() if (p / "task.yaml").exists())
        else:
            ids = [s.strip() for s in subset.split(",") if s.strip()]
        tasks = []
        for tid in ids:
            spec = yaml.safe_load((self._task_dir(tid) / "task.yaml").read_text())
            tasks.append(
                Task(
                    task_id=tid,
                    problem_statement=spec["problem_statement"],
                    dev_test_cmd=spec.get("dev_test_cmd", ""),
                    metadata=spec,
                )
            )
        return tasks

    def make_environment(self, task: Task) -> LocalEnvironment:
        tmp = tempfile.mkdtemp(prefix=f"agenteval_{task.task_id}_")
        src = self._task_dir(task.task_id) / "workspace"
        shutil.copytree(src, tmp, dirs_exist_ok=True)
        return LocalEnvironment(tmp)

    def evaluate(self, task: Task, patch: str) -> EvalResult:
        if not patch.strip():
            return EvalResult(False, {"reason": "empty_patch"})

        tmp = Path(tempfile.mkdtemp(prefix=f"agenteval_eval_{task.task_id}_"))
        try:
            # 1. fresh workspace
            shutil.copytree(self._task_dir(task.task_id) / "workspace", tmp, dirs_exist_ok=True)
            # 2. apply the agent's patch
            apply = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                input=patch, cwd=tmp, text=True, capture_output=True,
            )
            if apply.returncode != 0:
                # Fall back to `patch -p1` for diffs git is picky about.
                apply = subprocess.run(
                    ["patch", "-p1", "--forward"], input=patch, cwd=tmp,
                    text=True, capture_output=True,
                )
                if apply.returncode != 0:
                    return EvalResult(False, {"reason": "patch_apply_failed", "stderr": apply.stderr[:1000]})
            # 3. inject hidden oracle tests
            tests_src = self._task_dir(task.task_id) / "tests"
            if tests_src.exists():
                shutil.copytree(tests_src, tmp, dirs_exist_ok=True)
            # 4. run the eval command
            cmd = task.metadata.get("eval_test_cmd", "python -m pytest -q")
            timeout = float(task.metadata.get("timeout", 120))
            run = subprocess.run(
                cmd, shell=True, cwd=tmp, text=True, capture_output=True,
                timeout=timeout, env=sandbox_env(),
            )
            return EvalResult(
                resolved=run.returncode == 0,
                details={
                    "reason": "tests_passed" if run.returncode == 0 else "tests_failed",
                    "exit_code": run.returncode,
                    "output_tail": (run.stdout + run.stderr)[-2000:],
                },
            )
        except subprocess.TimeoutExpired:
            return EvalResult(False, {"reason": "eval_timeout"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
