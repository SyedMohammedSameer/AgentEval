"""Structured trajectory logging.

Every step the agent takes is recorded so failures can be classified after the fact
and runs are fully reproducible/auditable. Trajectories serialize to JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum


class ActionType(str, Enum):
    BASH = "bash"
    RUN_TESTS = "run_tests"
    SUBMIT = "submit"
    NONE = "none"          # model produced no parseable action
    ERROR = "error"        # harness-side error executing the step


@dataclass
class Step:
    index: int
    thought: str
    action_type: str
    action_input: str
    observation: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


@dataclass
class Trajectory:
    task_id: str
    run_name: str
    model: str
    steps: list[Step] = field(default_factory=list)
    # Outcome, filled in by the runner/evaluator.
    submitted: bool = False
    patch: str = ""
    resolved: bool = False               # did the produced patch pass the benchmark's tests
    stop_reason: str = ""                # "submit" | "max_steps" | "error" | "empty_patch"
    failure_mode: str = ""               # set by failure_taxonomy after eval
    eval_details: dict = field(default_factory=dict)
    wall_time_s: float = 0.0

    # --- aggregates ---
    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(s.prompt_tokens for s in self.steps)

    @property
    def total_completion_tokens(self) -> int:
        return sum(s.completion_tokens for s in self.steps)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["num_steps"] = self.num_steps
        d["total_prompt_tokens"] = self.total_prompt_tokens
        d["total_completion_tokens"] = self.total_completion_tokens
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
