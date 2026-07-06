"""Benchmark provider interface.

A provider knows how to (1) list tasks in a subset, (2) hand the agent a working
environment for a task, and (3) score a produced patch. Local and SWE-bench both
implement this, so the runner and failure taxonomy are benchmark-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..environments.base import Environment


@dataclass
class Task:
    task_id: str
    problem_statement: str
    # A test command the agent may run *during* solving (may be empty for real SWE-bench,
    # where the agent doesn't get the hidden tests). Used by the local `run_tests` tool.
    dev_test_cmd: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalResult:
    resolved: bool
    # Structured detail for the taxonomy: which tests passed/failed, error text, etc.
    details: dict = field(default_factory=dict)


class BenchmarkProvider(Protocol):
    name: str

    def load_tasks(self, subset: str) -> list[Task]:
        ...

    def make_environment(self, task: Task) -> Environment:
        """Fresh, isolated workspace for the agent to act in."""
        ...

    def evaluate(self, task: Task, patch: str) -> EvalResult:
        """Score a patch against the benchmark's hidden tests."""
        ...
