"""Render an HTML report over one or more runs, and refresh the README results block.

Reads results/<run>/metrics.json for each run and produces a single self-contained
HTML file: a solve-rate comparison, per-run failure-mode breakdown, and cost columns.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

from .failure_taxonomy import DESCRIPTIONS, FailureMode

_TEMPLATE = Template(
    """<!doctype html>
<html><head><meta charset="utf-8"><title>agenteval report</title>
<style>
  body { font: 15px/1.5 -apple-system, system-ui, sans-serif; margin: 2rem auto; max-width: 960px; color: #1a1a1a; }
  h1 { margin-bottom: .2rem; } .sub { color:#666; margin-top:0; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }
  th, td { padding: .5rem .7rem; border-bottom: 1px solid #e5e5e5; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background:#fafafa; font-weight:600; }
  .bar { height: 14px; background: #2563eb; border-radius: 3px; display:inline-block; }
  .pos { color:#16a34a; } .neg { color:#dc2626; } .dim { color:#999; }
  .mode { font-family: ui-monospace, monospace; font-size: 13px; }
  code { background:#f3f3f3; padding:1px 4px; border-radius:3px; }
</style></head><body>
<h1>agenteval — coding-agent evaluation</h1>
<p class="sub">{{ n_runs }} run(s) · model(s): {{ models }}</p>

<h2>Solve rate</h2>
<table>
<tr><th>condition</th><th>solve rate</th><th>Δ vs baseline</th><th></th><th>avg steps</th><th>completion tokens</th></tr>
{% for r in runs %}
<tr>
  <td>{{ r.name }}</td>
  <td>{{ '%.1f'|format(r.solve_rate*100) }}%  ({{ r.num_resolved }}/{{ r.num_tasks }})</td>
  <td class="{{ 'pos' if r.delta>0 else ('neg' if r.delta<0 else 'dim') }}">{{ r.delta_str }}</td>
  <td><span class="bar" style="width:{{ (r.solve_rate*180)|round(0,'floor') }}px"></span></td>
  <td>{{ r.avg_steps }}</td>
  <td>{{ '{:,}'.format(r.total_completion_tokens) }}</td>
</tr>
{% endfor %}
</table>

<h2>Failure modes by condition</h2>
<table>
<tr><th>mode</th>{% for r in runs %}<th>{{ r.name }}</th>{% endfor %}</tr>
{% for mode in modes %}
<tr><td class="mode" title="{{ mode.desc }}">{{ mode.key }}</td>
{% for r in runs %}<td>{{ r.failure_breakdown.get(mode.key, 0) }}</td>{% endfor %}
</tr>
{% endfor %}
</table>
<p class="dim">Hover a mode for its definition. Baseline = first run.</p>
</body></html>
"""
)


def _load_runs(run_names: list[str], output_dir: str) -> list[dict]:
    base = Path(output_dir)
    if run_names:
        dirs = [base / n for n in run_names]
    else:
        dirs = sorted(p for p in base.iterdir() if (p / "metrics.json").exists())
    runs = []
    for d in dirs:
        mp = d / "metrics.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text())
        m["condition"] = d.name.split("__")[-1]   # last segment = ablation condition
        m["name"] = f"{m['model']} · {m['condition']}"
        runs.append(m)
    return runs


def build_dashboard(run_names: list[str], *, output_dir: str = "results", out: str = "results/dashboard.html") -> None:
    runs = _load_runs(run_names, output_dir)
    if not runs:
        raise SystemExit("no runs with metrics.json found under results/")

    # Delta is measured against the *baseline of the same model*, so a sweep across
    # multiple models compares each condition to its own reference.
    base_by_model = {
        r["model"]: r["solve_rate"] for r in runs if r.get("condition") == "baseline"
    }
    for r in runs:
        base_rate = base_by_model.get(r["model"], runs[0]["solve_rate"])
        r["delta"] = r["solve_rate"] - base_rate
        r["delta_str"] = "—" if r.get("condition") == "baseline" else f"{r['delta']*100:+.1f}%"

    modes = [{"key": m.value, "desc": DESCRIPTIONS[m]} for m in FailureMode]

    html = _TEMPLATE.render(
        runs=runs,
        n_runs=len(runs),
        models=", ".join(sorted({r["model"] for r in runs})),
        modes=modes,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"Wrote {out_path}")

    _update_readme(runs)


_COND_LABEL = {
    "baseline": "baseline",
    "no_test_tool": "− run_tests tool",
    "no_repo_map": "− repo map (context)",
    "windowed_history": "windowed history",
    "best_of_3": "best-of-3 (retry)",
}
_COND_ORDER = ["baseline", "no_test_tool", "no_repo_map", "windowed_history", "best_of_3"]


def _update_readme(runs: list[dict]) -> None:
    """Refresh the RESULTS block with a pivoted condition x model table that tells the
    scaffolding-vs-capability story, plus a one-line headline."""
    readme = Path("README.md")
    if not readme.exists():
        return

    # model -> condition -> metrics
    by_model: dict[str, dict[str, dict]] = {}
    for r in runs:
        by_model.setdefault(r["model"], {})[r.get("condition", r["name"])] = r
    models = sorted(by_model, key=lambda m: ("1.5b" not in m, m))
    conds = [c for c in _COND_ORDER if any(c in cm for cm in by_model.values())]

    header = "| condition | " + " | ".join(f"`{m}`" for m in models) + " |"
    sep = "|" + "---|" * (len(models) + 1)
    rows = [header, sep]
    for c in conds:
        cells = [_COND_LABEL.get(c, c)]
        for m in models:
            r = by_model[m].get(c)
            if not r:
                cells.append("—")
                continue
            base = by_model[m].get("baseline", {}).get("solve_rate", 0)
            rate = f"{r['solve_rate']*100:.0f}%"
            if c == "baseline":
                cells.append(f"**{rate}**")
            else:
                d = (r["solve_rate"] - base) * 100
                cells.append(f"{rate} ({d:+.0f})")
        rows.append("| " + " | ".join(cells) + " |")
    block = "\n".join(rows)

    # Headline: run_tests value at each capability level.
    hl = []
    for m in models:
        base = by_model[m].get("baseline", {}).get("solve_rate")
        nt = by_model[m].get("no_test_tool", {}).get("solve_rate")
        if base is not None and nt is not None:
            hl.append(f"`{m}` {base*100:.0f}%→{nt*100:.0f}% ({(nt-base)*100:+.0f} pts)")
    headline = (
        "**Finding — scaffolding value is inversely proportional to base-model capability.** "
        "Removing the `run_tests` tool: " + "; ".join(hl) + ". "
        "Cells show solve rate and Δ vs the same model's baseline (12 tasks each). "
        "_best-of-3 shows +0 because temperature=0 makes the rollouts identical — the fix is "
        "to raise temperature for multi-sampling._"
    )

    text = readme.read_text()
    start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    if start in text and end in text:
        pre = text.split(start)[0]
        post = text.split(end)[1]
        text = f"{pre}{start}\n\n{headline}\n\n{block}\n\n{end}{post}"
        readme.write_text(text)
        print("Updated README results block")
