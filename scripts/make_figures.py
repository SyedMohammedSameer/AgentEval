"""Figures for the write-up, derived from the run rather than transcribed.

    python scripts/make_figures.py data/steps.jsonl figures/

Every number plotted is recomputed from steps.jsonl, so a figure cannot drift
away from the table it illustrates.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402

from agentverif.report import (correctness_shift, group_runs,  # noqa: E402
                               headline, load_steps,
                               paired_arm_correctness, wilson)

# White rather than the off-white chart surface: these are placed on a printed
# page, and #fcfcfb reads as a visible grey panel against it.
SURFACE, INK, MUTED = "#ffffff", "#0b0b0b", "#52514e"
BLUE, ORANGE, GRID = "#2a78d6", "#eb6834", "#e3e2df"
SHORT = {"deepseek-coder-6.7b": "DeepSeek 6.7B", "granite-8b-code": "Granite 8B",
         "qwen2.5-coder-7b": "Qwen2.5 7B", "yi-coder-9b": "Yi 9B"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "font.size": 9, "text.color": INK, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8,
    "font.family": "DejaVu Sans",
})


def bare(ax, xgrid=True):
    """Recessive axes: the data carries the figure, not the furniture."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    if xgrid:
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)


def shown_ruff_pairs(steps):
    """(codes shown, broke) for every task whose baseline passed and whose ruff
    arm ran - the population the breakage claims are about."""
    out = []
    for _key, run in group_runs(steps).items():
        base = run["baseline"]
        if not base or base.get("error") or not base["tests_passed"]:
            continue
        arm = [s for s in run["arms"].get("shown_ruff", []) if not s.get("error")]
        codes = [c for c, _ in (base.get("findings") or {}).get("ruff", [])]
        if arm and codes:
            out.append((codes, not arm[-1]["tests_passed"]))
    return out


def fig_rule_family(steps, out):
    """The headline, scoped to what survives its own robustness check.

    Grouping by "security rule vs not" looked like a four-fold effect until S311
    was held out, at which point the intervals overlapped. S311 is 91 of the 122
    security-shown tasks, so that grouping was reporting one rule under a class
    name. Splitting it out is the honest picture and is still the striking one.
    """
    pairs = shown_ruff_pairs(steps)
    sec = lambda c: any(x[0] == "S" for x in c)
    groups = {"S311 among the\nfindings shown":
              [(c, b) for c, b in pairs if "S311" in c],
              "Other security rule,\nno S311":
              [(c, b) for c, b in pairs if "S311" not in c and sec(c)],
              "No security rule\nat all":
              [(c, b) for c, b in pairs if not sec(c)]}

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, (label, rows) in enumerate(groups.items()):
        n = len(rows)
        k = sum(b for _, b in rows)
        rate = k / n
        lo, hi = wilson(k, n)
        ax.barh(i, rate, height=0.42, color=BLUE,
                xerr=[[rate - lo], [hi - rate]],
                error_kw=dict(ecolor=MUTED, lw=1.2, capsize=4))
        ax.text(hi + 0.015, i, f"{rate:.1%}   [{lo:.0%}, {hi:.0%}]   n={n}",
                va="center", fontsize=9, color=INK)

    ax.set_yticks(range(len(groups)), list(groups), fontsize=9, color=INK)
    ax.set_xlim(0, 0.72)
    ax.set_xticks([0, .1, .2, .3, .4, .5], ["0%", "10%", "20%", "30%", "40%", "50%"])
    ax.set_xlabel("working programs broken by the repair", labelpad=8)
    ax.invert_yaxis()
    bare(ax)
    ax.set_title("One rule accounts for the damage",
                 loc="left", fontsize=11, color=INK, pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def fig_paired(steps, out):
    """The controlled comparison: same task, same model, same baseline."""
    rows = [r for r in paired_arm_correctness(steps) if r["model"] != "ALL"]
    ys = range(len(rows))
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    h = 0.34
    for i, r in enumerate(rows):
        ax.barh(i - h / 2 - 0.02, r["ruff_only"], height=h, color=BLUE)
        ax.barh(i + h / 2 + 0.02, r["pylint_only"], height=h, color=ORANGE)
        ax.text(r["ruff_only"] + 0.3, i - h / 2 - 0.02, str(r["ruff_only"]),
                va="center", fontsize=8.5, color=INK)
        ax.text(r["pylint_only"] + 0.3, i + h / 2 + 0.02, str(r["pylint_only"]),
                va="center", fontsize=8.5, color=INK)
        ax.text(17.4, i, f"p = {r['p_exact']:.3g}", va="center", fontsize=8.5,
                color=MUTED)

    ax.set_yticks(list(ys), [f"{SHORT[r['model']]}\n{r['n_pairs']} pairs" for r in rows],
                  fontsize=8.5, color=INK)
    ax.set_xlim(0, 21)
    ax.set_xticks(range(0, 21, 5))     # discordant pairs are counts, not fractions
    ax.set_xlabel("tasks where one arm broke the program and the other did not",
                  labelpad=8)
    ax.invert_yaxis()
    bare(ax)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE),
                       plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
              labels=["shown Ruff broke it", "shown Pylint broke it"],
              frameon=False, ncol=2, loc="lower right", fontsize=8.5,
              bbox_to_anchor=(1.0, -0.42))
    ax.set_title("Within the same task, on the same model's own solution",
                 loc="left", fontsize=11, color=INK, pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def fig_by_rule(steps, out, min_n=8):
    per = defaultdict(lambda: [0, 0])
    for codes, broke in shown_ruff_pairs(steps):
        for c in set(codes):
            per[c][0] += broke
            per[c][1] += 1
    rows = sorted(((c, k, n) for c, (k, n) in per.items() if n >= min_n),
                  key=lambda r: r[1] / r[2])

    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    for i, (code, k, n) in enumerate(rows):
        rate = k / n
        ax.barh(i, rate, height=0.5, color=BLUE)
        ax.text(rate + 0.012, i, f"{rate:.0%}   n={n}", va="center",
                fontsize=8.5, color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=9, color=INK)
    ax.set_xlim(0, 0.78)
    ax.set_xticks([0, .2, .4, .6], ["0%", "20%", "40%", "60%"])
    ax.set_xlabel("working programs broken when this rule was among those shown",
                  labelpad=8)
    bare(ax)
    ax.set_title("Breakage by rule: the fixes that change what the code does",
                 loc="left", fontsize=11, color=INK, pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def fig_suppression(steps, out):
    """The result the study was built to find, and did not."""
    rows = [r for r in headline(steps) if r["arm"] == "shown_ruff"]
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    for i, r in enumerate(rows):
        rate = r["suppression_rate"]
        lo, hi = r["suppression_ci"]
        ax.barh(i, rate, height=0.44, color=BLUE,
                xerr=[[rate - lo], [hi - rate]],
                error_kw=dict(ecolor=MUTED, lw=1.2, capsize=4))
        ax.text(hi + 0.012, i, f"{rate:.0%}   [{lo:.0%}, {hi:.0%}]   n={r['measurable']}",
                va="center", fontsize=8.5, color=INK)
    ax.axvline(0.5, color=ORANGE, lw=2, ls=(0, (4, 3)))
    ax.text(0.5, -0.92, "  what systematic gaming would look like",
            fontsize=8.5, color=ORANGE, va="center")

    ax.set_yticks(range(len(rows)), [SHORT[r["model"]] for r in rows],
                  fontsize=9, color=INK)
    ax.set_xlim(0, 0.62)
    ax.set_xticks([0, .1, .2, .3, .4, .5], ["0%", "10%", "20%", "30%", "40%", "50%"])
    ax.set_xlabel("removed from Ruff but still reported by Bandit", labelpad=8)
    ax.invert_yaxis()
    bare(ax)
    ax.set_ylim(len(rows) - 0.4, -1.3)
    ax.set_title("The agents did not game the analyser they were shown",
                 loc="left", fontsize=11, color=INK, pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/steps.jsonl"
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "figures")
    outdir.mkdir(parents=True, exist_ok=True)
    steps = load_steps(path)
    if not steps:
        raise SystemExit(f"no steps at {path}")

    jobs = [("fig1_breakage_by_rule_group.png", fig_rule_family),
            ("fig2_paired_arms.png", fig_paired),
            ("fig3_by_rule.png", fig_by_rule),
            ("fig4_no_gaming.png", fig_suppression)]
    for name, fn in jobs:
        fn(steps, outdir / name)
        print(f"wrote {outdir / name}")


if __name__ == "__main__":
    main()
