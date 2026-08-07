"""Controlled ablations: hold everything fixed, flip ONE lever, measure the delta.

Each condition differs from the baseline by exactly one field, so any solve-rate
change is attributable to that lever. This is the core evidence the harness
produces: not "the agent scores X%" but "feature Y is worth +Z points, and here is
the interval and the p-value that claim rests on."

Two design points worth stating explicitly, because both were bugs first:

**Best-of-N needs its own control.** Multi-sampling requires temperature > 0 to draw
distinct rollouts, so `best_of_3` differs from the temperature-0 baseline in *two*
fields and cannot be compared to it. `sampling_control` closes that gap: same
temperature, one attempt. The retry lever is `best_of_3` vs `sampling_control`;
comparing it to `baseline` instead would confound retries with sampling temperature.

**Conditions are replicated across seeds.** A single run of a condition is one draw
from a noisy process. Seeds do not add independent evidence about an effect (tasks
do — see `stats.required_tasks`), but they do stop a single unlucky rollout from
becoming a published number.
"""

from __future__ import annotations

from dataclasses import replace

from rich.console import Console
from rich.table import Table

from .aggregate import compare_to_baseline, coverage_warnings, load_conditions
from .config import AgentConfig, ModelConfig, RunConfig
from .metrics import RunMetrics
from .runner import run

console = Console()

# Temperature used by every condition that draws more than one sample. High enough
# to give best-of-N something to select over, low enough to keep the agent coherent.
SAMPLING_TEMPERATURE = 0.8


def _baseline_agent() -> AgentConfig:
    return AgentConfig(
        max_steps=20,
        use_test_tool=True,
        include_repo_map=True,
        history_strategy="full",
        self_check=True,
        attempts=1,
    )


# condition -> (agent overrides, model overrides, what it is compared against)
SUITES: dict[str, list[tuple[str, dict, dict, str]]] = {
    "core": [
        ("baseline", {}, {}, ""),
        # --- tool availability ---
        ("no_test_tool", {"use_test_tool": False}, {}, "baseline"),
        # --- context construction ---
        ("no_repo_map", {"include_repo_map": False}, {}, "baseline"),
        ("windowed_history", {"history_strategy": "windowed", "history_window": 8}, {}, "baseline"),
        # --- retry / pass@k. Control first so the pair reads in order. ---
        ("sampling_control", {}, {"temperature": SAMPLING_TEMPERATURE}, "baseline"),
        ("best_of_3", {"attempts": 3}, {"temperature": SAMPLING_TEMPERATURE}, "sampling_control"),
    ],
}

# Which condition each one is contrasted against, for reporting.
REFERENCE = {cond: ref for suite in SUITES.values() for cond, _, _, ref in suite}


def run_suite(
    suite: str,
    *,
    model: str,
    subset: str,
    provider: str,
    seeds: list[int] | None = None,
    output_dir: str = "results",
) -> list[RunMetrics]:
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}; have {list(SUITES)}")

    seeds = seeds or [0]
    base_agent = _baseline_agent()
    model_label = ModelConfig(model=model).label()
    results: list[RunMetrics] = []

    total = len(SUITES[suite]) * len(seeds)
    console.rule(f"[bold]Suite '{suite}'  model={model}  {len(seeds)} seed(s)  {total} runs")

    for cond_name, agent_override, model_override, _ref in SUITES[suite]:
        for seed in seeds:
            agent_cfg = replace(base_agent, **agent_override)
            model_cfg = replace(ModelConfig(model=model), **model_override)
            cfg = RunConfig(
                # Model and seed both live in the run name so sweeps never overwrite
                # each other and the aggregator can group them back together.
                name=f"{suite}__{model_label}__{cond_name}__s{seed}",
                provider=provider,
                subset=subset,
                model=model_cfg,
                agent=agent_cfg,
                seed=seed,
                output_dir=output_dir,
            )
            results.append(run(cfg))

    report(suite, output_dir=output_dir)
    return results


def report(suite: str | None = None, *, output_dir: str = "results") -> None:
    """Print the pooled cross-condition table with intervals and paired p-values."""
    conditions = load_conditions(output_dir, suite=suite)
    if not conditions:
        console.print("[yellow]No runs found to report.[/]")
        return

    comparisons = compare_to_baseline(conditions)
    console.rule(f"[bold]Ablation comparison{f': {suite}' if suite else ''}")

    for model in sorted({m for m, _ in conditions}):
        table = Table(show_header=True, header_style="bold", title=model)
        table.add_column("condition")
        table.add_column("solve rate (95% CI)", justify="right")
        table.add_column("vs", justify="left")
        table.add_column("Δ [95% CI]", justify="right")
        table.add_column("p", justify="right")
        table.add_column("seeds", justify="right")

        ordered = [c for c, *_ in SUITES.get(suite or "core", [])] or sorted(
            c for m, c in conditions if m == model
        )
        for cond in ordered:
            cs = conditions.get((model, cond))
            if cs is None:
                continue
            if not cs.num_tasks:
                # A run from before per-task outcomes were recorded. Showing 0/0 here
                # would read as a genuine 0% rather than as missing data.
                table.add_row(cond, "[dim]no per-task data[/]", "—", "—", "—", str(len(cs.seeds)))
                continue
            lo, hi = cs.solve_rate_ci
            rate = f"{cs.solve_rate:.0%} ({cs.num_resolved}/{cs.num_tasks}) [{lo:.0%}-{hi:.0%}]"

            ref = REFERENCE.get(cond, "baseline")
            cmp_ = comparisons.get((model, cond))
            if cond == "baseline" or cmp_ is None:
                table.add_row(cond, rate, "—", "—", "—", str(len(cs.seeds)))
                continue

            # Re-pair against the declared reference when it isn't the baseline.
            if ref and ref != "baseline":
                ref_cs = conditions.get((model, ref))
                if ref_cs is not None:
                    from .stats import compare as _compare

                    cmp_ = _compare(ref_cs.task_labels, cs.task_labels)

            d_lo, d_hi = cmp_.delta_ci
            sig = "[green]" if cmp_.significant else "[dim]"
            table.add_row(
                cond,
                rate,
                ref or "—",
                f"{cmp_.delta * 100:+.0f} [{d_lo * 100:+.0f},{d_hi * 100:+.0f}]",
                f"{sig}{cmp_.p_value:.3f}{'*' if cmp_.significant else ''}[/]",
                str(len(cs.seeds)),
            )
        console.print(table)

    for w in coverage_warnings(conditions):
        console.print(f"[yellow]![/] {w}")

    console.print(
        "[dim]Δ is percentage points vs the 'vs' column, paired over tasks; "
        "p is an exact McNemar test. * = p<0.05. "
        "Task labels are majority-vote across seeds.[/]"
    )
    console.print("[dim]Render the full report with:  agenteval dashboard[/]")
