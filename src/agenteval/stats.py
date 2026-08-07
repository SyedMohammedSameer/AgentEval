"""Uncertainty quantification for solve-rate comparisons.

An eval harness that reports a bare percentage over a dozen tasks is reporting
noise with extra steps. Everything here exists to attach an honest error bar to a
number before it goes in a table.

Two facts drive the choices below:

1. **n is small.** Solve rate is a binomial proportion over ~12-60 tasks, where the
   normal approximation is badly behaved (and degenerate at p=0 or p=1). We use the
   Wilson score interval, which stays inside [0,1] and holds its nominal coverage
   down to single-digit n.

2. **Conditions are paired.** Every ablation runs the *same tasks* as the baseline,
   so "baseline vs no_test_tool" is a paired design, not two independent samples.
   The correct test is McNemar's, which conditions on the tasks where the two
   conditions disagree and throws away the (uninformative) tasks where they agree.
   Treating paired data as unpaired — a Fisher/chi-square 2x2 on the marginals —
   discards the pairing and gives up power for nothing.

Pairing is not a substitute for sample size, and `required_tasks` exists to make
that concrete *before* a sweep is launched rather than after. Exact McNemar cannot
return anything under 0.05 until at least six tasks flip the same way
(2 x 0.5^6 = 0.031), so a 12-task benchmark cannot certify even a very large
effect. Checking power is cheaper than a run that was never able to conclude.

Pure stdlib: no scipy dependency for a few dozen lines of combinatorics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import comb, sqrt

# 97.5th percentile of the standard normal — the multiplier for a two-sided 95% CI.
Z_95 = 1.959963985


# --------------------------------------------------------------------------- CIs


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n.

    Preferred over the textbook normal ("Wald") interval, which at these sample
    sizes produces intervals that fall outside [0,1] and collapse to zero width
    when k is 0 or n — exactly the cases an eval hits when a condition solves
    nothing or everything.
    """
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def format_rate_ci(k: int, n: int) -> str:
    """`42% [18-71]` — a solve rate that carries its own uncertainty."""
    if n <= 0:
        return "n/a"
    lo, hi = wilson_interval(k, n)
    return f"{k / n * 100:.0f}% [{lo * 100:.0f}-{hi * 100:.0f}]"


# ------------------------------------------------------------------- hypothesis


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar test for paired binary outcomes.

    `b` = tasks the first condition solved and the second did not.
    `c` = tasks the second solved and the first did not.
    Tasks both solved or both failed carry no information about a difference and
    are correctly excluded.

    Under the null the b+c discordant tasks split 50/50, so this is an exact
    two-sided binomial test at p=0.5. Exact rather than the chi-square
    approximation because b+c is routinely under 10 here.
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test on a 2x2 table [[a, b], [c, d]].

    For *unpaired* comparisons only — e.g. contrasting two different models, which
    do not share a task-level pairing in any meaningful sense. For two conditions
    of the same model on the same tasks, use `mcnemar_exact`.
    """
    n = a + b + c + d
    if n == 0:
        return 1.0
    row1, col1 = a + b, a + c

    def hyper(x: int) -> float:
        return comb(row1, x) * comb(n - row1, col1 - x) / comb(n, col1)

    observed = hyper(a)
    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)
    # Sum every table at least as extreme as the observed one.
    return min(1.0, sum(hyper(x) for x in range(lo, hi + 1) if hyper(x) <= observed + 1e-12))


# ------------------------------------------------------------------------ power


def min_discordant_for_significance(alpha: float = 0.05) -> int:
    """Fewest one-directional flips exact McNemar needs to clear `alpha`.

    A hard floor set by the test itself, independent of how many tasks were run: if
    an ablation flips only four tasks, the smallest p it can return is 0.125 and no
    amount of careful reporting will make it significant.
    """
    b = 1
    while mcnemar_exact(b, 0) > alpha and b < 1000:
        b += 1
    return b


def power_mcnemar(
    n_tasks: int,
    flip_rate: float,
    *,
    reverse_rate: float = 0.0,
    alpha: float = 0.05,
    iterations: int = 4000,
    seed: int = 0,
) -> float:
    """Probability a run of `n_tasks` detects an effect of size `flip_rate`.

    `flip_rate` is the share of tasks the ablation is expected to break (baseline
    solved, condition did not); `reverse_rate` the share it accidentally fixes.
    Simulated rather than derived because the exact test's discreteness makes the
    closed form misleading at these sizes.
    """
    rng = random.Random(seed)
    hits = 0
    for _ in range(iterations):
        b = c = 0
        for _ in range(n_tasks):
            r = rng.random()
            if r < flip_rate:
                b += 1
            elif r < flip_rate + reverse_rate:
                c += 1
        if mcnemar_exact(b, c) < alpha:
            hits += 1
    return hits / iterations


def required_tasks(
    flip_rate: float,
    *,
    target_power: float = 0.8,
    reverse_rate: float = 0.0,
    alpha: float = 0.05,
    max_n: int = 400,
) -> int | None:
    """Smallest task count reaching `target_power`, or None if `max_n` isn't enough.

    Answers the only question worth asking before committing GPU-hours to a sweep:
    is this benchmark large enough to conclude anything? Note that seeds are not a
    substitute for tasks here — repeated seeds on the same 12 tasks tighten the
    estimate of *those* tasks' difficulty, they do not add independent evidence
    about the effect.
    """
    for n in range(4, max_n + 1, 2):
        if power_mcnemar(n, flip_rate, reverse_rate=reverse_rate, alpha=alpha) >= target_power:
            return n
    return None


# -------------------------------------------------------------------- bootstrap


def paired_bootstrap_delta(
    baseline: dict[str, bool],
    condition: dict[str, bool],
    *,
    iterations: int = 10000,
    seed: int = 0,
) -> tuple[float, float]:
    """95% CI for the solve-rate *difference*, resampling tasks (not rollouts).

    Resamples task ids with replacement, keeping each task's baseline and condition
    outcomes together so the pairing survives. This answers the question a reader
    actually has — "would this delta hold on a different draw of tasks?" — which is
    the dominant source of uncertainty when the benchmark has a dozen items.

    Seeded, so a rendered report is byte-identical across runs.
    """
    shared = sorted(set(baseline) & set(condition))
    if not shared:
        return (0.0, 0.0)

    rng = random.Random(seed)
    n = len(shared)
    deltas = []
    for _ in range(iterations):
        picks = [shared[rng.randrange(n)] for _ in range(n)]
        b = sum(baseline[t] for t in picks) / n
        c = sum(condition[t] for t in picks) / n
        deltas.append(c - b)
    deltas.sort()
    return (deltas[int(0.025 * iterations)], deltas[int(0.975 * iterations) - 1])


# ---------------------------------------------------------------- comparison


@dataclass
class Comparison:
    """A condition measured against its baseline, with uncertainty attached."""

    n_tasks: int
    baseline_resolved: int
    condition_resolved: int
    delta: float                 # condition rate - baseline rate, in [-1, 1]
    delta_ci: tuple[float, float]
    p_value: float               # exact McNemar, paired
    n_discordant: int            # tasks where the two conditions disagreed
    gained: list[str]            # solved by condition, not baseline
    lost: list[str]              # solved by baseline, not condition

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def summary(self) -> str:
        stars = "*" if self.significant else ""
        lo, hi = self.delta_ci
        return (
            f"{self.delta * 100:+.0f} pts [{lo * 100:+.0f}, {hi * 100:+.0f}] "
            f"p={self.p_value:.3f}{stars}"
        )


def compare(baseline: dict[str, bool], condition: dict[str, bool], *, seed: int = 0) -> Comparison:
    """Paired comparison of two conditions evaluated on the same task set.

    Only tasks present in both are used, so a partial or interrupted run degrades to
    a smaller honest comparison rather than a silently wrong one.
    """
    shared = sorted(set(baseline) & set(condition))
    n = len(shared)
    lost = [t for t in shared if baseline[t] and not condition[t]]
    gained = [t for t in shared if condition[t] and not baseline[t]]

    b_res = sum(1 for t in shared if baseline[t])
    c_res = sum(1 for t in shared if condition[t])
    delta = (c_res - b_res) / n if n else 0.0

    return Comparison(
        n_tasks=n,
        baseline_resolved=b_res,
        condition_resolved=c_res,
        delta=delta,
        delta_ci=paired_bootstrap_delta(baseline, condition, seed=seed),
        p_value=mcnemar_exact(len(lost), len(gained)),
        n_discordant=len(lost) + len(gained),
        gained=gained,
        lost=lost,
    )
