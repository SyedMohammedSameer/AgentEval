"""Aggregate metrics over a set of trajectories for a run."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from .trajectory import Trajectory


@dataclass
class RunMetrics:
    run_name: str
    model: str
    num_tasks: int
    num_resolved: int
    solve_rate: float
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    avg_steps: float = 0.0
    avg_wall_time_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    # For best-of-N runs: how many tasks needed >1 attempt.
    attempts_used: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(run_name: str, model: str, best: list[Trajectory], all_attempts: list[Trajectory]) -> RunMetrics:
    """`best` = one trajectory per task (resolved one if any). `all_attempts` = every rollout."""
    n = len(best)
    resolved = sum(1 for t in best if t.resolved)
    breakdown = Counter(t.failure_mode for t in best)
    return RunMetrics(
        run_name=run_name,
        model=model,
        num_tasks=n,
        num_resolved=resolved,
        solve_rate=round(resolved / n, 4) if n else 0.0,
        failure_breakdown=dict(breakdown),
        avg_steps=round(sum(t.num_steps for t in best) / n, 2) if n else 0.0,
        avg_wall_time_s=round(sum(t.wall_time_s for t in best) / n, 2) if n else 0.0,
        total_prompt_tokens=sum(t.total_prompt_tokens for t in all_attempts),
        total_completion_tokens=sum(t.total_completion_tokens for t in all_attempts),
    )
