"""The Environment interface the agent acts through.

A benchmark provides a concrete Environment (local subprocess sandbox, or a SWE-bench
Docker container). The agent only ever sees `exec` + patch operations, so the same
agent loop runs unchanged across benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ExecResult:
    stdout: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@runtime_checkable
class Environment(Protocol):
    workdir: str

    def exec(self, cmd: str, timeout: float = 60.0) -> ExecResult:
        """Run a shell command in the workspace and return combined stdout/stderr."""
        ...

    def get_patch(self) -> str:
        """Return the agent's edits as a unified git diff against the base state."""
        ...

    def repo_map(self, max_entries: int = 200) -> str:
        """A compact listing of tracked files, for context construction."""
        ...

    def teardown(self) -> None:
        ...
