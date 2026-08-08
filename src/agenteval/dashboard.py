"""Render an HTML report over one or more runs, and refresh the README results block.

Reads every run under results/, pools replicate seeds per condition, and produces a
single self-contained HTML file.

The report is built so that no solve rate ever appears without its confidence
interval and no delta ever appears without its p-value. That constraint is the whole
point: a bare "42% vs 58%" invites a conclusion the underlying twelve-task sample
cannot support, and the fastest way to stop publishing that claim is to make the
interval impossible to omit.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from .aggregate import ConditionSummary, compare_to_baseline, coverage_warnings, load_conditions
from .failure_taxonomy import DESCRIPTIONS, FailureMode
from .stats import Comparison

_TEMPLATE = Template(
    """<!doctype html>
<html><head><meta charset="utf-8"><title>agenteval report</title>
<style>
  body { font: 15px/1.55 -apple-system, system-ui, sans-serif; margin: 2rem auto;
         max-width: 1040px; color: #1a1a1a; padding: 0 1rem; }
  h1 { margin-bottom: .2rem; } .sub { color:#666; margin-top:0; }
  h2 { margin-top: 2.2rem; border-bottom: 1px solid #eee; padding-bottom: .3rem; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; }
  th, td { padding: .45rem .6rem; border-bottom: 1px solid #e5e5e5; text-align: right;
           vertical-align: middle; }
  th:first-child, td:first-child { text-align: left; }
  th { background:#fafafa; font-weight:600; font-size: 13px; }
  .pos { color:#16a34a; } .neg { color:#dc2626; } .dim { color:#999; }
  .sig { font-weight: 600; }
  .mode { font-family: ui-monospace, monospace; font-size: 13px; }
  code { background:#f3f3f3; padding:1px 4px; border-radius:3px; font-size: 13px; }
  .note { background:#fffbeb; border-left:3px solid #f59e0b; padding:.6rem .9rem;
          margin:.8rem 0; font-size:14px; }
  .caveat { color:#666; font-size:13px; margin-top:.4rem; }
  /* A solve rate drawn as a point with its Wilson interval, so the eye reads the
     uncertainty at the same time as the estimate. */
  .ci { position:relative; height:16px; width:200px; display:inline-block;
        background:#f5f5f5; border-radius:3px; }
  .ci .band { position:absolute; height:6px; top:5px; background:#bfdbfe; border-radius:3px; }
  .ci .dot  { position:absolute; width:8px; height:12px; top:2px; background:#2563eb;
              border-radius:2px; margin-left:-4px; }
  .taskflip { font-family: ui-monospace, monospace; font-size:12px; color:#555; }
</style></head><body>
<h1>agenteval — coding-agent evaluation</h1>
<p class="sub">{{ n_tasks }} tasks · model(s): {{ models }} · {{ n_runs }} run(s)</p>

{% for w in warnings %}<div class="note">{{ w }}</div>{% endfor %}

{% for block in blocks %}
<h2>{{ block.model }}</h2>
<table>
<tr>
  <th>condition</th><th>solve rate</th><th>95% CI</th><th></th>
  <th>vs</th><th>Δ pts [95% CI]</th><th>p</th><th>seeds</th><th>compl. tokens</th>
</tr>
{% for r in block.rows %}
<tr>
  <td>{{ r.condition }}</td>
  <td>{{ r.rate }}</td>
  <td class="dim">{{ r.ci }}</td>
  <td><span class="ci">
        <span class="band" style="left:{{ r.ci_lo_px }}px; width:{{ r.ci_w_px }}px"></span>
        <span class="dot" style="left:{{ r.point_px }}px"></span>
      </span></td>
  <td class="dim">{{ r.reference }}</td>
  <td class="{{ r.delta_class }}">{{ r.delta }}</td>
  <td class="{{ 'sig' if r.significant else 'dim' }}">{{ r.p }}</td>
  <td class="dim">{{ r.seeds }}</td>
  <td class="dim">{{ r.tokens }}</td>
</tr>
{% if r.flips %}
<tr><td colspan="9" class="taskflip">↳ {{ r.flips }}</td></tr>
{% endif %}
{% endfor %}
</table>
{% endfor %}

<h2>Failure modes by condition</h2>
<table>
<tr><th>mode</th>{% for c in mode_cols %}<th>{{ c }}</th>{% endfor %}</tr>
{% for mode in modes %}
<tr><td class="mode" title="{{ mode.desc }}">{{ mode.key }}</td>
{% for c in mode_cols %}<td>{{ mode.counts.get(c, 0) }}</td>{% endfor %}
</tr>
{% endfor %}
</table>
<p class="caveat">Counts are summed across seeds, so they total (tasks x seeds) per
column. Hover a mode for its definition.</p>

<h2>How to read this</h2>
<p class="caveat">
Solve rate is the share of tasks solved in a majority of seeds; the interval is a
95% Wilson score interval over tasks. Δ is measured against the condition named in
the <em>vs</em> column, paired task-by-task, and p is an exact McNemar test on the
tasks where the two conditions disagreed. Seeds reduce label noise but are not
independent evidence about an effect — only tasks are — so both the interval and the
test are computed over tasks, never over rollouts.
</p>
</body></html>
"""
)


def _px(fraction: float, width: int = 200) -> int:
    return round(max(0.0, min(1.0, fraction)) * width)


def _row(cs: ConditionSummary, reference: str, cmp_: Comparison | None) -> dict:
    lo, hi = cs.solve_rate_ci
    row = {
        "condition": cs.condition,
        "rate": f"{cs.solve_rate * 100:.0f}% ({cs.num_resolved}/{cs.num_tasks})",
        "ci": f"{lo * 100:.0f}–{hi * 100:.0f}%",
        "ci_lo_px": _px(lo),
        "ci_w_px": max(2, _px(hi) - _px(lo)),
        "point_px": _px(cs.solve_rate),
        "seeds": len(cs.seeds),
        "tokens": f"{cs.total_completion_tokens:,}",
        "reference": reference or "—",
        "delta": "—",
        "delta_class": "dim",
        "p": "—",
        "significant": False,
        "flips": "",
    }
    if cmp_ is None:
        return row

    d_lo, d_hi = cmp_.delta_ci
    row["delta"] = f"{cmp_.delta * 100:+.0f} [{d_lo * 100:+.0f}, {d_hi * 100:+.0f}]"
    row["delta_class"] = "pos" if cmp_.delta > 0 else ("neg" if cmp_.delta < 0 else "dim")
    row["p"] = f"{cmp_.p_value:.3f}"
    row["significant"] = cmp_.significant

    # The tasks that actually moved are the mechanism behind the number.
    bits = []
    if cmp_.lost:
        bits.append(f"broke: {', '.join(cmp_.lost[:6])}" + (" …" if len(cmp_.lost) > 6 else ""))
    if cmp_.gained:
        bits.append(f"fixed: {', '.join(cmp_.gained[:6])}" + (" …" if len(cmp_.gained) > 6 else ""))
    row["flips"] = " · ".join(bits)
    return row


def build_dashboard(
    run_names: list[str],
    *,
    output_dir: str = "results",
    out: str = "results/dashboard.html",
    suite: str | None = None,
) -> None:
    conditions = load_conditions(output_dir, suite=suite)
    if run_names:
        wanted = set(run_names)
        conditions = {k: v for k, v in conditions.items() if v.condition in wanted or f"{v.model}" in wanted}
    conditions = {k: v for k, v in conditions.items() if v.num_tasks}
    if not conditions:
        raise SystemExit(
            "no runs with per-task outcomes found under "
            f"{output_dir}/ — run `agenteval ablate` to produce some"
        )

    comparisons = compare_to_baseline(conditions)

    from .ablation import REFERENCE, SUITES
    from .stats import compare as _compare

    ordered_conditions = [c for c, *_ in SUITES.get(suite or "core", [])]

    blocks = []
    for model in sorted({m for m, _ in conditions}):
        model_conds = {c: cs for (m, c), cs in conditions.items() if m == model}
        order = [c for c in ordered_conditions if c in model_conds]
        order += [c for c in sorted(model_conds) if c not in order]

        rows = []
        for cond in order:
            cs = model_conds[cond]
            ref = "" if cond == "baseline" else REFERENCE.get(cond, "baseline")
            cmp_ = None
            if ref:
                ref_cs = model_conds.get(ref)
                cmp_ = (
                    _compare(ref_cs.task_labels, cs.task_labels)
                    if ref_cs is not None
                    else comparisons.get((model, cond))
                )
            rows.append(_row(cs, ref, cmp_))
        blocks.append({"model": model, "rows": rows})

    mode_cols = [f"{m} · {c}" for (m, c) in sorted(conditions)]
    modes = []
    for m in FailureMode:
        counts = {
            f"{model} · {cond}": cs.failure_breakdown.get(m.value, 0)
            for (model, cond), cs in conditions.items()
        }
        if any(counts.values()):
            modes.append({"key": m.value, "desc": DESCRIPTIONS[m], "counts": counts})

    html = _TEMPLATE.render(
        blocks=blocks,
        modes=modes,
        mode_cols=mode_cols,
        models=", ".join(sorted({m for m, _ in conditions})),
        n_runs=sum(len(cs.seeds) for cs in conditions.values()),
        n_tasks=max(cs.num_tasks for cs in conditions.values()),
        warnings=coverage_warnings(conditions),
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"Wrote {out_path}")

    _update_readme(conditions, comparisons)


_COND_LABEL = {
    "baseline": "baseline",
    "no_test_tool": "− run_tests tool",
    "no_repo_map": "− repo map (context)",
    "windowed_history": "windowed history",
    "sampling_control": "sampling control (T>0)",
    "best_of_3": "best-of-3 (pass@3, oracle-selected)",
    "best_of_3_dev": "best-of-3 (visible-test selected)",
}
_COND_ORDER = [
    "baseline", "no_test_tool", "no_repo_map",
    "windowed_history", "sampling_control", "best_of_3", "best_of_3_dev",
]


def _update_readme(
    conditions: dict[tuple[str, str], ConditionSummary],
    comparisons: dict[tuple[str, str], Comparison],
) -> None:
    """Refresh the RESULTS block with a condition x model table.

    Every cell carries its interval and every delta its p-value, so the block cannot
    be copied into a post as a bare set of percentages.
    """
    readme = Path("README.md")
    if not readme.exists():
        return

    models = sorted({m for m, _ in conditions}, key=lambda m: ("1.5b" not in m, m))
    conds = [c for c in _COND_ORDER if any((m, c) in conditions for m in models)]
    if not conds or not models:
        return

    n_tasks = max(cs.num_tasks for cs in conditions.values())
    n_seeds = max(len(cs.seeds) for cs in conditions.values())

    header = "| condition | " + " | ".join(f"`{m}`" for m in models) + " |"
    rows = [header, "|" + "---|" * (len(models) + 1)]
    for c in conds:
        cells = [_COND_LABEL.get(c, c)]
        for m in models:
            cs = conditions.get((m, c))
            if cs is None:
                cells.append("—")
                continue
            lo, hi = cs.solve_rate_ci
            rate = f"{cs.solve_rate * 100:.0f}% [{lo * 100:.0f}–{hi * 100:.0f}]"
            if c == "baseline":
                cells.append(f"**{rate}**")
            else:
                cmp_ = comparisons.get((m, c))
                if cmp_ is None:
                    cells.append(rate)
                else:
                    star = "\\*" if cmp_.significant else ""
                    cells.append(f"{rate}<br>{cmp_.delta * 100:+.0f} pts, p={cmp_.p_value:.2f}{star}")
        rows.append("| " + " | ".join(cells) + " |")
    block = "\n".join(rows)

    significant = [
        (m, c, cmp_) for (m, c), cmp_ in sorted(comparisons.items()) if cmp_.significant
    ]
    if significant:
        m, c, cmp_ = max(significant, key=lambda t: abs(t[2].delta))
        headline = (
            f"**Largest measured effect — `{_COND_LABEL.get(c, c)}` on `{m}`: "
            f"{cmp_.delta * 100:+.0f} points** "
            f"(95% CI {cmp_.delta_ci[0] * 100:+.0f} to {cmp_.delta_ci[1] * 100:+.0f}, "
            f"exact McNemar p={cmp_.p_value:.3f}, n={cmp_.n_tasks} tasks)."
        )
    else:
        headline = (
            "**No condition reached significance.** Every interval below includes zero — "
            "reported as a null result rather than as a trend."
        )

    footer = (
        f"Cells show solve rate with a 95% Wilson interval, and the paired delta vs the "
        f"reference condition with an exact McNemar p-value. {n_tasks} tasks x {n_seeds} "
        f"seed(s) per condition; a task counts as solved if it succeeded in a majority of "
        f"seeds. \\* marks p<0.05."
    )

    text = readme.read_text()
    start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    if start in text and end in text:
        pre = text.split(start)[0]
        post = text.split(end)[1]
        text = f"{pre}{start}\n\n{headline}\n\n{block}\n\n{footer}\n\n{end}{post}"
        readme.write_text(text)
        print("Updated README results block")
