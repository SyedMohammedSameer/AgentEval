"""Re-derive every figure quoted in the README from the raw run.

    python scripts/verify_readme.py data/steps.jsonl

A paper's numbers should be checkable by the person reading it, not trusted
because they were once printed by a notebook. Every claim in the README that is a
number appears here with the value it asserts, and this script fails if the data
stops agreeing with it.
"""
from __future__ import annotations

import sys

from agentverif.report import (common_tasks, correctness_shift, headline,
                               load_steps, paired_arm_correctness,
                               suppression_directives, traded_defects)

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/steps.jsonl"
steps = load_steps(PATH)
if not steps:
    raise SystemExit(f"no steps at {PATH}")

failures = []


def chk(label, got, want):
    good = got == want
    if not good:
        failures.append(label)
    print(f"{'ok ' if good else 'BAD'} {label:50s} {got}"
          + ("" if good else f"   README says {want}"))


chk("steps", len(steps), 4439)
chk("models", len({s["model"] for s in steps}), 4)
chk("shared tasks", len(common_tasks(steps)), 300)

h = {(r["model"], r["arm"]): r for r in headline(steps)}
for m, want in [("deepseek-coder-6.7b", (152, 62, 0.02)),
                ("granite-8b-code", (110, 53, 0.08)),
                ("qwen2.5-coder-7b", (179, 78, 0.12)),
                ("yi-coder-9b", (208, 90, 0.03))]:
    r = h[(m, "shown_ruff")]
    chk(f"{m} addressed/measurable/rate",
        (r["addressed"], r["measurable"], round(r["suppression_rate"], 2)), want)

pool = {r["arm"]: r for r in headline(steps, by_model=False)}
pr = pool["shown_ruff"]
chk("pooled ruff addressed/measurable", (pr["addressed"], pr["measurable"]), (649, 283))
chk("pooled suppression + CI",
    (round(pr["suppression_rate"], 2), tuple(round(x, 2) for x in pr["suppression_ci"])),
    (0.06, (0.04, 0.09)))
chk("pylint arm has no measurable transfers", pool["shown_pylint"]["measurable"], 0)
chk("ruff addressed rate 70%", round(pr["addressed_rate"] * 100), 70)
chk("pylint addressed rate 20%", round(pool["shown_pylint"]["addressed_rate"] * 100), 20)

chk("directives written across the study",
    sum(v for r in suppression_directives(steps)
        for k, v in r.items() if k not in ("model", "arm")), 5)

pa = {r["model"]: r for r in paired_arm_correctness(steps)}
cells = lambda r: (r["n_pairs"], r["ruff_only"], r["pylint_only"], r["both"], r["neither"])
chk("paired pooled (pairs,ruff,pylint,both,neither)", cells(pa["ALL"]), (213, 46, 3, 5, 159))
chk("paired p < 1e-10", pa["ALL"]["p_exact"] < 1e-10, True)
chk("every model individually significant",
    all(pa[m]["p_exact"] < 0.05 for m in pa if m != "ALL"), True)
for m, want in [("deepseek-coder-6.7b", (46, 9, 1, 1, 35)),
                ("granite-8b-code", (49, 10, 0, 0, 39)),
                ("qwen2.5-coder-7b", (56, 12, 0, 4, 40)),
                ("yi-coder-9b", (62, 15, 2, 0, 45))]:
    chk(f"{m} paired row", cells(pa[m]), want)

cs = correctness_shift(steps)
agg = lambda arm, k: sum(r[k] for r in cs if r["arm"] == arm)
chk("ruff arm broke/passing", (agg("shown_ruff", "broke"), agg("shown_ruff", "pass_before")), (51, 213))
chk("pylint arm broke/passing", (agg("shown_pylint", "broke"), agg("shown_pylint", "pass_before")), (14, 368))
chk("S602->S603 swaps observed", traded_defects(steps).get("ruff:S603"), 3)

print(f"\n{'FAILED: ' + ', '.join(failures) if failures else 'all README figures verified'}")
sys.exit(1 if failures else 0)
