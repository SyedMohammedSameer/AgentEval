"""Aggregate metrics over a set of trajectories for a run.

`task_results` is the load-bearing field: it records *which* tasks were solved, not
just how many. Ablation conditions run the same task set, so keeping the per-task
outcomes is what makes a paired comparison (see `stats.compare`) possible at all —
a bare solve-rate percentage cannot be tested against another percentage without
throwing away the pairing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from .stats import wilson_interval
from .trajectory import Trajectory


@dataclass
class RunMetrics:
    run_name: str
    model: str
    num_tasks: int
    num_resolved: int
    solve_rate: float
    # 95% Wilson interval on solve_rate. Reported everywhere the rate is, so a
    # number is never shown without the uncertainty that belongs to it.
    solve_rate_ci: tuple[float, float] = (0.0, 0.0)
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    # task_id -> resolved. The basis of every paired significance test downstream.
    task_results: dict[str, bool] = field(default_factory=dict)
    # task_id -> failure mode, for per-task drilldown in the dashboard.
    task_modes: dict[str, str] = field(default_factory=dict)
    seed: int = 0
    temperature: float = 0.0
    avg_steps: float = 0.0
    avg_wall_time_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    # For best-of-N runs: how many tasks needed >1 attempt.
    attempts_used: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["solve_rate_ci"] = list(self.solve_rate_ci)
        return d


def summarize(
    run_name: str,
    model: str,
    best: list[Trajectory],
    all_attempts: list[Trajectory],
    *,
    seed: int = 0,
    temperature: float = 0.0,
) -> RunMetrics:
    """`best` = one trajectory per task (resolved one if any). `all_attempts` = every rollout."""
    n = len(best)
    resolved = sum(1 for t in best if t.resolved)
    breakdown = Counter(t.failure_mode for t in best)

    # How many rollouts each task consumed — best-of-N only spends extra attempts
    # on tasks it hasn't solved yet, so this is the real cost of the retry lever.
    attempts_per_task = Counter(t.task_id for t in all_attempts)

    return RunMetrics(
        run_name=run_name,
        model=model,
        num_tasks=n,
        num_resolved=resolved,
        solve_rate=round(resolved / n, 4) if n else 0.0,
        solve_rate_ci=wilson_interval(resolved, n),
        failure_breakdown=dict(breakdown),
        task_results={t.task_id: t.resolved for t in best},
        task_modes={t.task_id: t.failure_mode for t in best},
        seed=seed,
        temperature=temperature,
        avg_steps=round(sum(t.num_steps for t in best) / n, 2) if n else 0.0,
        avg_wall_time_s=round(sum(t.wall_time_s for t in best) / n, 2) if n else 0.0,
        total_prompt_tokens=sum(t.total_prompt_tokens for t in all_attempts),
        total_completion_tokens=sum(t.total_completion_tokens for t in all_attempts),
        attempts_used=dict(attempts_per_task),
    )
