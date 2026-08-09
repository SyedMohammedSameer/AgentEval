"""Aggregate a completed study into the numbers that go in the paper.

Runs entirely offline over the JSONL the study writes, so the analysis can be
re-derived, re-sliced by severity, and corrected without touching a GPU.

Every rate carries a Wilson interval. At the sample sizes this study reaches, a
bare percentage invites a conclusion the data cannot support, and the interval is
the cheapest way to stop that happening.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from math import comb, sqrt

from .transfer import fates_for_arm, introduced_codes, summarise

Z_95 = 1.959963985


def wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Interval for a proportion. Wilson rather than the normal approximation,
    which falls outside [0,1] and collapses to zero width at k=0 or k=n, both of
    which this study will hit on small per-model slices."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_steps(path: str) -> list[dict]:
    """Steps from a checkpoint, tolerating both ways a run ends badly: a file
    that was never written because every model failed, and a final line cut in
    half by a session timeout."""
    rows: list[dict] = []
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def group_runs(steps: list[dict]) -> dict:
    """(task, model) -> {"baseline": step, arm: [steps in round order]}."""
    runs: dict = defaultdict(lambda: {"baseline": None, "arms": defaultdict(list)})
    for s in steps:
        key = (s["task_id"], s["model"])
        if s["arm"] == "baseline":
            runs[key]["baseline"] = s
        else:
            runs[key]["arms"][s["arm"]].append(s)
    for r in runs.values():
        for arm, lst in r["arms"].items():
            lst.sort(key=lambda s: s["round"])
    return runs


def common_tasks(steps: list[dict]) -> set:
    """Task ids that every model completed a baseline for.

    Each model walks the same fixed shuffle, so a model that runs out of time
    holds a prefix of that order and the per-model task sets are nested. Comparing
    models on the union would compare them on different tasks; restricting to this
    intersection keeps the cross-model contrast paired. Both are worth reporting -
    the per-model rate uses everything that model did, the cross-model table uses
    this.

    A model with no usable baseline anywhere is not counted: it contributes no
    rows to any table, so letting it zero the shared set would throw away the
    models that did work.
    """
    by_model: dict = defaultdict(set)
    for s in steps:
        if s["arm"] == "baseline" and not s.get("error"):
            by_model[s["model"]].add(s["task_id"])
    if not by_model:
        return set()
    return set.intersection(*by_model.values())


def restrict(steps: list[dict], task_ids: set) -> list[dict]:
    return [s for s in steps if s["task_id"] in task_ids]


def collect_fates(steps: list[dict]) -> list:
    """Fate of every baseline finding, using each arm's final successful round."""
    out = []
    for run in group_runs(steps).values():
        base = run["baseline"]
        if not base or base.get("error"):
            continue
        for _arm, rounds in run["arms"].items():
            usable = [s for s in rounds if not s.get("error")]
            if usable:
                out.extend(fates_for_arm(base, usable[-1]))
    return out


def headline(steps: list[dict], by_model: bool = True) -> list[dict]:
    """Suppression rate per (model, arm), which is the paper's headline number."""
    fates = collect_fates(steps)
    buckets: dict = defaultdict(list)
    for f in fates:
        buckets[(f.model if by_model else "all", f.arm)].append(f)

    rows = []
    for (model, arm), group in sorted(buckets.items()):
        s = summarise(group)
        lo, hi = (wilson(s["measurable"] - s["transferred"], s["measurable"])
                  if s["measurable"] else (0.0, 0.0))
        rows.append({**s, "model": model, "arm": arm,
                     "suppression_ci": (lo, hi)})
    return rows


def correctness_shift(steps: list[dict]) -> list[dict]:
    """Did repair break working code?

    Tracked per arm because a fix that removes a finding by breaking the function
    is a different failure from one that hides it, and the two must not be pooled.
    """
    rows = []
    buckets: dict = defaultdict(lambda: {"n": 0, "pass_before": 0, "pass_after": 0,
                                         "broke": 0, "repaired": 0})
    for run in group_runs(steps).values():
        base = run["baseline"]
        if not base or base.get("error"):
            continue
        for arm, rounds in run["arms"].items():
            usable = [s for s in rounds if not s.get("error")]
            if not usable:
                continue
            last = usable[-1]
            b = buckets[(base["model"], arm)]
            b["n"] += 1
            b["pass_before"] += bool(base["tests_passed"])
            b["pass_after"] += bool(last["tests_passed"])
            if base["tests_passed"] and not last["tests_passed"]:
                b["broke"] += 1
            if not base["tests_passed"] and last["tests_passed"]:
                b["repaired"] += 1

    for (model, arm), b in sorted(buckets.items()):
        rows.append({"model": model, "arm": arm, **b,
                     "broke_rate": b["broke"] / b["n"] if b["n"] else 0.0})
    return rows


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pairs.

    Exact rather than the chi-square approximation because the discordant counts
    here are small enough that the approximation is not trustworthy, and binomial
    tails at this size cost nothing to compute.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def paired_arm_correctness(steps: list[dict]) -> list[dict]:
    """Does repairing security findings break more code than repairing lint?

    The two arms cover different task sets - ruff only fires on about half of
    them - so comparing their raw breakage rates compares different work. This
    restricts to (task, model) pairs where *both* arms ran and the baseline
    passed its tests, which makes every comparison within one task on one model's
    own solution. `b` and `c` are the discordant pairs, and they are the whole
    test: pairs where both arms broke it, or neither did, say nothing about which
    arm is worse.
    """
    per_model: dict = defaultdict(lambda: {"both": 0, "ruff_only": 0,
                                           "pylint_only": 0, "neither": 0})
    for (task, model), run in group_runs(steps).items():
        base = run["baseline"]
        if not base or base.get("error") or not base["tests_passed"]:
            continue
        broke = {}
        for arm in ("shown_pylint", "shown_ruff"):
            usable = [s for s in run["arms"].get(arm, []) if not s.get("error")]
            if usable:
                broke[arm] = not usable[-1]["tests_passed"]
        if len(broke) < 2:
            continue        # only one arm ran; not a pair
        cell = ("both" if broke["shown_ruff"] and broke["shown_pylint"] else
                "ruff_only" if broke["shown_ruff"] else
                "pylint_only" if broke["shown_pylint"] else "neither")
        per_model[model][cell] += 1

    rows = []
    pooled = {"both": 0, "ruff_only": 0, "pylint_only": 0, "neither": 0}
    for model, t in sorted(per_model.items()):
        for k in pooled:
            pooled[k] += t[k]
        rows.append({"model": model, **t, "n_pairs": sum(t.values()),
                     "p_exact": mcnemar_exact(t["ruff_only"], t["pylint_only"])})
    if rows:
        rows.append({"model": "ALL", **pooled, "n_pairs": sum(pooled.values()),
                     "p_exact": mcnemar_exact(pooled["ruff_only"],
                                              pooled["pylint_only"])})
    return rows


def suppression_directives(steps: list[dict]) -> list[dict]:
    """Directives the agent actually wrote, which is the mechanism made countable
    rather than inferred from finding counts."""
    buckets: dict = defaultdict(lambda: defaultdict(int))
    for s in steps:
        if s["arm"] == "baseline" or s.get("error"):
            continue
        for tool, n in (s.get("suppressions_added") or {}).items():
            buckets[(s["model"], s["arm"])][tool] += n
    return [{"model": m, "arm": a, **dict(v)} for (m, a), v in sorted(buckets.items())]


def traded_defects(steps: list[dict]) -> dict:
    """Codes introduced by repair, counted across the study.

    A repair that swaps one defect for another leaves counts flat, so without
    this it is invisible.
    """
    counts: dict = defaultdict(int)
    for run in group_runs(steps).values():
        base = run["baseline"]
        if not base or base.get("error"):
            continue
        for _arm, rounds in run["arms"].items():
            usable = [s for s in rounds if not s.get("error")]
            if not usable:
                continue
            for tool, codes in introduced_codes(base, usable[-1]).items():
                for c in codes:
                    counts[f"{tool}:{c}"] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def format_headline(rows: list[dict]) -> str:
    out = [f"{'model':22s} {'arm':14s} {'findings':>9s} {'addressed':>10s} "
           f"{'measurable':>11s} {'suppressed':>11s} {'95% CI':>14s}"]
    for r in rows:
        rate = r["suppression_rate"]
        lo, hi = r["suppression_ci"]
        rate_s = "n/a" if rate is None else f"{rate:.0%}"
        ci_s = "-" if rate is None else f"[{lo:.0%}, {hi:.0%}]"
        out.append(f"{r['model']:22s} {r['arm']:14s} {r['findings']:>9d} "
                   f"{r['addressed']:>10d} {r['measurable']:>11d} "
                   f"{rate_s:>11s} {ci_s:>14s}")
    return "\n".join(out)
