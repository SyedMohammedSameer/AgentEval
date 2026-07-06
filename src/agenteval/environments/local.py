"""A Docker-free sandbox: the workspace is a temp directory under git.

Used by the synthetic local benchmark. Commands run as subprocesses with the workspace
as CWD. `get_patch` is `git diff` against the initial commit, so the produced patch has
the same shape as a SWE-bench prediction and flows through the identical downstream code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import ExecResult


def sandbox_env() -> dict[str, str]:
    """Environment for sandbox subprocesses: put the harness's own interpreter first on
    PATH so bare `python`/`pytest` resolve to one that actually has pytest installed
    (the system python may not)."""
    env = os.environ.copy()
    bindir = os.path.dirname(sys.executable)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    return env


class LocalEnvironment:
    def __init__(self, workdir: str | Path):
        self.workdir = str(workdir)
        self._git(["init", "-q"])
        self._git(["config", "user.email", "agent@eval.local"])
        self._git(["config", "user.name", "agenteval"])
        self._git(["add", "-A"])
        self._git(["commit", "-q", "-m", "base", "--allow-empty"])

    def _git(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.workdir, capture_output=True, text=True
        )

    def exec(self, cmd: str, timeout: float = 60.0) -> ExecResult:
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=self.workdir, capture_output=True,
                text=True, timeout=timeout, env=sandbox_env(),
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            return ExecResult(stdout=out, exit_code=proc.returncode)
        except subprocess.TimeoutExpired:
            return ExecResult(stdout=f"[command timed out after {timeout}s]", exit_code=124)

    def get_patch(self) -> str:
        # Stage everything so new files show up in the diff, then diff against base commit.
        self._git(["add", "-A"])
        proc = self._git(["diff", "--cached", "HEAD"])
        return proc.stdout

    def repo_map(self, max_entries: int = 200) -> str:
        files: list[str] = []
        root = Path(self.workdir)
        for p in sorted(root.rglob("*")):
            if ".git" in p.parts:
                continue
            if p.is_file():
                files.append(str(p.relative_to(root)))
            if len(files) >= max_entries:
                files.append("... (truncated)")
                break
        return "\n".join(files)

    def teardown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)
