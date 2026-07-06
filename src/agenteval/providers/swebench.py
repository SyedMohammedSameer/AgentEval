"""SWE-bench provider — runs the *same* agent loop against real GitHub-issue tasks.

The agent acts inside the instance's official Docker container (repo checked out at the
base commit at /testbed); scoring uses the official `swebench` evaluation harness, so
numbers are directly comparable to the public leaderboard.

Heavy deps (`datasets`, `swebench`) and Docker are only needed here — hence the lazy
imports. See docs/swebench.md for Apple-Silicon setup.
"""

from __future__ import annotations

import json
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path

from .base import EvalResult, Task

DATASET = "princeton-nlp/SWE-bench_Verified"


def _arch() -> str:
    return "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"


class SWEBenchEnvironment:
    """A live Docker container for one instance; the agent acts via `docker exec`."""

    def __init__(self, container_id: str, workdir: str = "/testbed"):
        self.container_id = container_id
        self.workdir = workdir

    def _docker_exec(self, cmd: str, timeout: float) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "exec", "-w", self.workdir, self.container_id, "bash", "-lc", cmd],
            capture_output=True, text=True, timeout=timeout,
        )

    def exec(self, cmd: str, timeout: float = 60.0):
        from ..environments.base import ExecResult

        try:
            p = self._docker_exec(cmd, timeout)
            return ExecResult(stdout=(p.stdout or "") + (p.stderr or ""), exit_code=p.returncode)
        except subprocess.TimeoutExpired:
            return ExecResult(stdout=f"[timed out after {timeout}s]", exit_code=124)

    def get_patch(self) -> str:
        # Diff only tracked source files; exclude test files (SWE-bench convention).
        p = self._docker_exec("git add -A && git diff --cached HEAD", timeout=60)
        return p.stdout

    def repo_map(self, max_entries: int = 200) -> str:
        p = self._docker_exec(
            "git ls-files | head -n %d" % max_entries, timeout=30
        )
        return p.stdout

    def teardown(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.container_id], capture_output=True)


class SWEBenchProvider:
    name = "swebench"

    def __init__(self, dataset: str = DATASET):
        self.dataset = dataset
        self._rows: dict[str, dict] = {}

    # ------------------------------------------------------------------ tasks
    def load_tasks(self, subset: str) -> list[Task]:
        from datasets import load_dataset

        ds = load_dataset(self.dataset, split="test")
        by_id = {r["instance_id"]: r for r in ds}
        self._rows = by_id

        ids = self._resolve_subset(subset, list(by_id))
        tasks = []
        for iid in ids:
            r = by_id[iid]
            tasks.append(
                Task(
                    task_id=iid,
                    problem_statement=r["problem_statement"],
                    dev_test_cmd="",  # hidden tests are not exposed to the agent
                    metadata={"repo": r["repo"], "base_commit": r["base_commit"]},
                )
            )
        return tasks

    def _resolve_subset(self, subset: str, all_ids: list[str]) -> list[str]:
        # A named file under subsets/, or a comma-separated id list, or "all".
        if subset == "all":
            return all_ids
        subset_file = Path("subsets") / f"{subset}.txt"
        if subset_file.exists():
            ids = [ln.strip() for ln in subset_file.read_text().splitlines()
                   if ln.strip() and not ln.startswith("#")]
        else:
            ids = [s.strip() for s in subset.split(",") if s.strip()]
        missing = [i for i in ids if i not in all_ids]
        if missing:
            raise ValueError(f"instance ids not in {self.dataset}: {missing[:3]}...")
        return ids

    # ------------------------------------------------------------ environment
    def make_environment(self, task: Task) -> SWEBenchEnvironment:
        from swebench.harness.test_spec.test_spec import make_test_spec

        spec = make_test_spec(self._rows[task.task_id])
        image = spec.instance_image_key  # official, correctly-encoded image name
        name = f"agenteval-{task.task_id}-{uuid.uuid4().hex[:6]}".lower().replace("/", "-")

        run = subprocess.run(
            ["docker", "run", "-d", "--name", name, image, "tail", "-f", "/dev/null"],
            capture_output=True, text=True,
        )
        if run.returncode != 0:
            raise RuntimeError(
                f"Could not start container from image {image!r}. Is it built/pulled? "
                f"docker error: {run.stderr.strip()}"
            )
        env = SWEBenchEnvironment(run.stdout.strip())
        # Ensure a clean base state.
        env.exec(f"git reset --hard {task.metadata['base_commit']} && git clean -fdx", timeout=120)
        return env

    # -------------------------------------------------------------- evaluate
    def evaluate(self, task: Task, patch: str) -> EvalResult:
        if not patch.strip():
            return EvalResult(False, {"reason": "empty_patch"})

        run_id = f"agenteval_{uuid.uuid4().hex[:8]}"
        tmp = Path(tempfile.mkdtemp(prefix="agenteval_swe_"))
        preds = tmp / "preds.jsonl"
        preds.write_text(json.dumps({
            "instance_id": task.task_id,
            "model_name_or_path": "agenteval",
            "model_patch": patch,
        }) + "\n")

        cmd = [
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", self.dataset,
            "--predictions_path", str(preds),
            "--instance_ids", task.task_id,
            "--run_id", run_id,
            "--max_workers", "1",
            "--cache_level", "instance",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        # The harness writes a report json: agenteval.<run_id>.json in CWD.
        report = Path(f"agenteval.{run_id}.json")
        if report.exists():
            data = json.loads(report.read_text())
            resolved = task.task_id in data.get("resolved_ids", [])
            reason = "tests_passed" if resolved else "tests_failed"
            return EvalResult(resolved, {"reason": reason, "report": data})
        return EvalResult(False, {"reason": "eval_error", "stderr": proc.stderr[-1500:]})
