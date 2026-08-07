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
    agent = Agent(cfg.model, cfg.agent, run_name=cfg.name, seed=cfg.seed)

    out_dir = Path(cfg.output_dir) / cfg.name
    traj_dir = out_dir / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)

    console.rule(
        f"[bold]Run '{cfg.name}'  model={cfg.model.model}  provider={cfg.provider}  "
        f"tasks={len(tasks)}  seed={cfg.seed}  T={cfg.model.temperature}"
    )
    for w in cfg.warnings():
        console.print(f"[yellow]warning:[/] {w}")

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

    metrics = summarize(
        cfg.name,
        cfg.model.model,
        best_per_task,
        every_attempt,
        seed=cfg.seed,
        temperature=cfg.model.temperature,
    )

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
    lo, hi = m.solve_rate_ci
    table.add_row(
        "solve rate",
        f"{m.solve_rate:.1%}  ({m.num_resolved}/{m.num_tasks})  [95% CI {lo:.0%}-{hi:.0%}]",
    )
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

    for note in headroom_warnings(m):
        console.print(f"[yellow]![/] {note}")


def headroom_warnings(m: RunMetrics) -> list[str]:
    """Flag a tier that arithmetically cannot yield a significant ablation.

    Power analysis asks whether *enough* tasks would flip. This asks the blunter
    prior question: how many tasks are even able to flip. An ablation that removes
    a capability can only break tasks the baseline solved, and one that adds a
    capability can only fix tasks it failed. Either count can sit below the six
    one-directional flips exact McNemar needs for p<0.05, in which case no seed
    count and no sample size rescues the comparison — the tier is the problem.

    Worth knowing after a single ~10-minute baseline probe rather than after an
    overnight sweep that was never able to conclude.
    """
    from .stats import min_discordant_for_significance

    floor = min_discordant_for_significance()
    unsolved = m.num_tasks - m.num_resolved
    notes = []

    if 0 < m.num_resolved < floor:
        notes.append(
            f"floor: only {m.num_resolved} of {m.num_tasks} tasks solved. An ablation that "
            f"removes a capability can flip at most {m.num_resolved}, and exact McNemar needs "
            f"{floor} to reach p<0.05 — so no negative result on this tier can be significant. "
            "Raise --max-steps or move to a stronger model before sweeping."
        )
    if 0 < unsolved < floor:
        notes.append(
            f"ceiling: only {unsolved} of {m.num_tasks} tasks unsolved. An ablation can improve "
            f"at most {unsolved}, below the {floor} flips needed for p<0.05 — this tier is too "
            "strong for the task set to measure anything on."
        )
    if m.num_resolved == 0:
        notes.append(
            f"this tier solved nothing; every condition will read 0% and every delta +0. "
            "Fix the tier or the step budget before spending a sweep on it."
        )
    return notes
