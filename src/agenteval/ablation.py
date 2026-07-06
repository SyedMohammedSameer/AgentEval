"""Controlled ablations: hold everything fixed, flip ONE lever, measure the delta.

Each condition differs from the baseline by exactly one AgentConfig field, so any
solve-rate change is attributable to that lever. This is the core evidence the harness
produces: not "the agent scores X%" but "feature Y is worth +Z points."
"""

from __future__ import annotations

from dataclasses import replace

from rich.console import Console
from rich.table import Table

from .config import AgentConfig, ModelConfig, RunConfig
from .metrics import RunMetrics
from .runner import run

console = Console()


def _baseline_agent() -> AgentConfig:
    return AgentConfig(
        max_steps=20,
        use_test_tool=True,
        include_repo_map=True,
        history_strategy="full",
        self_check=True,
        attempts=1,
    )


# suite -> list of (condition_name, agent_config_override_kwargs)
SUITES: dict[str, list[tuple[str, dict]]] = {
    "core": [
        ("baseline", {}),
        ("no_test_tool", {"use_test_tool": False}),      # tool-use ablation
        ("no_repo_map", {"include_repo_map": False}),    # context-construction ablation
        ("windowed_history", {"history_strategy": "windowed", "history_window": 8}),
        ("best_of_3", {"attempts": 3}),                  # retry / pass@k ablation
    ],
}


def run_suite(suite: str, *, model: str, subset: str, provider: str) -> list[RunMetrics]:
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}; have {list(SUITES)}")

    base_agent = _baseline_agent()
    model_label = ModelConfig(model=model).label()
    results: list[RunMetrics] = []
    for cond_name, override in SUITES[suite]:
        agent_cfg = replace(base_agent, **override)
        cfg = RunConfig(
            # model in the run name so sweeps across models don't overwrite each other.
            name=f"{suite}__{model_label}__{cond_name}",
            provider=provider,
            subset=subset,
            model=ModelConfig(model=model),
            agent=agent_cfg,
        )
        results.append(run(cfg))

    _print_comparison(suite, results)
    return results


def _print_comparison(suite: str, results: list[RunMetrics]) -> None:
    console.rule(f"[bold]Ablation comparison: {suite}")
    base = results[0].solve_rate
    table = Table(show_header=True, header_style="bold")
    table.add_column("condition")
    table.add_column("solve rate", justify="right")
    table.add_column("Δ vs baseline", justify="right")
    table.add_column("avg steps", justify="right")
    table.add_column("compl. tokens", justify="right")
    for m in results:
        delta = m.solve_rate - base
        cond = m.run_name.split("__")[-1]
        dstr = "—" if cond == "baseline" else f"{delta:+.1%}"
        table.add_row(
            cond, f"{m.solve_rate:.1%}", dstr, f"{m.avg_steps}", f"{m.total_completion_tokens:,}"
        )
    console.print(table)
    console.print("[dim]Render the full report with:  agenteval dashboard[/]")
