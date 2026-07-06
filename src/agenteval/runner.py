"""Orchestrates a full run: tasks -> agent rollouts -> evaluation -> taxonomy -> metrics.

Writes per-task trajectories and a run summary under results/<run_name>/, which the
dashboard and ablation tooling read back.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agent import Agent
from .config import RunConfig
from .failure_taxonomy import annotate
from .metrics import RunMetrics, summarize
from .providers import get_provider
from .providers.base import Task
from .trajectory import Trajectory

console = Console()


def _run_task(agent: Agent, provider, task: Task, attempts: int) -> tuple[Trajectory, list[Trajectory]]:
    """Run up to `attempts` rollouts; stop early once resolved. Returns (best, all)."""
    all_attempts: list[Trajectory] = []
    best: Trajectory | None = None
    for attempt in range(attempts):
        env = provider.make_environment(task)
        try:
            traj = agent.rollout(task, env, attempt)
        finally:
            pass
        ev = provider.evaluate(task, traj.patch)
        traj.resolved = ev.resolved
        traj.eval_details = ev.details
        annotate(traj)
        env.teardown()
        all_attempts.append(traj)
        if best is None or (traj.resolved and not best.resolved):
            best = traj
        if traj.resolved:
            break
    return best, all_attempts  # type: ignore[return-value]


def run(cfg: RunConfig) -> RunMetrics:
    provider = get_provider(cfg.provider)
    tasks = provider.load_tasks(cfg.subset)
    agent = Agent(cfg.model, cfg.agent, run_name=cfg.name)

    out_dir = Path(cfg.output_dir) / cfg.name
    traj_dir = out_dir / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold]Run '{cfg.name}'  model={cfg.model.model}  provider={cfg.provider}  tasks={len(tasks)}")

    best_per_task: list[Trajectory] = []
    every_attempt: list[Trajectory] = []
    t_start = time.monotonic()

    for i, task in enumerate(tasks, 1):
        console.print(f"[cyan]({i}/{len(tasks)})[/] {task.task_id} ...", end=" ")
        best, attempts = _run_task(agent, provider, task, cfg.agent.attempts)
        best_per_task.append(best)
        every_attempt.extend(attempts)

        status = "[green]RESOLVED[/]" if best.resolved else f"[red]{best.failure_mode}[/]"
        console.print(f"{status}  ({best.num_steps} steps, {best.wall_time_s:.0f}s)")

        (traj_dir / f"{task.task_id}.json").write_text(best.to_json())

    metrics = summarize(cfg.name, cfg.model.model, best_per_task, every_attempt)

    # Persist run artifacts.
    (out_dir / "config.json").write_text(json.dumps(cfg.to_dict(), indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics.to_dict(), indent=2))

    _print_summary(metrics, time.monotonic() - t_start)
    return metrics


def _print_summary(m: RunMetrics, wall: float) -> None:
    console.rule(f"[bold]Summary: {m.run_name}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("solve rate", f"{m.solve_rate:.1%}  ({m.num_resolved}/{m.num_tasks})")
    table.add_row("avg steps", f"{m.avg_steps}")
    table.add_row("avg wall time", f"{m.avg_wall_time_s}s")
    table.add_row("completion tokens", f"{m.total_completion_tokens:,}")
    table.add_row("total wall", f"{wall:.0f}s")
    console.print(table)

    if m.failure_breakdown:
        ft = Table(show_header=True, header_style="bold", title="failure modes")
        ft.add_column("mode")
        ft.add_column("count", justify="right")
        for mode, cnt in sorted(m.failure_breakdown.items(), key=lambda x: -x[1]):
            ft.add_row(mode, str(cnt))
        console.print(ft)
