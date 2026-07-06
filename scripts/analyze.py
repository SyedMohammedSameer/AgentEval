"""Cross-model ablation analysis.

Loads every core-suite run under results/, groups by model, and prints a condition x model
matrix of solve rates plus per-model deltas vs that model's baseline. The headline it
surfaces: how the *value of each scaffolding lever* changes with base-model capability.

Run: python scripts/analyze.py
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

RESULTS = Path("results")
console = Console()

# Nice display order / labels for the core suite.
COND_ORDER = ["baseline", "no_test_tool", "no_repo_map", "windowed_history", "best_of_3"]
COND_LABEL = {
    "baseline": "baseline",
    "no_test_tool": "− run_tests tool",
    "no_repo_map": "− repo map (context)",
    "windowed_history": "windowed history",
    "best_of_3": "best-of-3 (retry)",
}


def load() -> dict[str, dict[str, dict]]:
    """model -> condition -> metrics."""
    out: dict[str, dict[str, dict]] = {}
    for d in sorted(RESULTS.glob("core__*")):
        mp = d / "metrics.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text())
        cond = d.name.split("__")[-1]
        out.setdefault(m["model"], {})[cond] = m
    return out


def main() -> None:
    data = load()
    if not data:
        raise SystemExit("no core__* runs found. Run: agenteval ablate --suite core")

    models = sorted(data, key=lambda m: ("1.5b" not in m, m))  # weaker model first

    table = Table(title="Solve rate by condition x model  (Δ vs same-model baseline)",
                  show_header=True, header_style="bold")
    table.add_column("condition")
    for model in models:
        table.add_column(model, justify="right")

    for cond in COND_ORDER:
        row = [COND_LABEL.get(cond, cond)]
        for model in models:
            m = data[model].get(cond)
            if not m:
                row.append("—")
                continue
            base = data[model].get("baseline", {}).get("solve_rate", 0)
            rate = m["solve_rate"]
            if cond == "baseline":
                row.append(f"{rate:.0%}")
            else:
                d = rate - base
                sign = "+" if d >= 0 else ""
                row.append(f"{rate:.0%} ({sign}{d*100:.0f})")
        table.add_row(*row)
    console.print(table)

    # Headline: value of the run_tests tool at each capability level.
    console.print("\n[bold]Headline — value of the run_tests tool by base-model capability:[/]")
    for model in models:
        base = data[model].get("baseline", {}).get("solve_rate")
        no_tool = data[model].get("no_test_tool", {}).get("solve_rate")
        if base is None or no_tool is None:
            continue
        drop = (base - no_tool) * 100
        console.print(f"  {model:24s} removing run_tests: {base:.0%} → {no_tool:.0%}  ([red]−{drop:.0f} pts[/])" if drop > 0
                      else f"  {model:24s} removing run_tests: {base:.0%} → {no_tool:.0%}  (no effect)")


if __name__ == "__main__":
    main()
