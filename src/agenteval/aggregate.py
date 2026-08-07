"""Pool repeated runs of the same condition and compare conditions honestly.

A single run of a condition gives one draw. Replicating it across seeds gives a
better estimate of *that task set's* difficulty — which is why this module exists —
but seeds are not extra tasks, and conflating the two is the easiest way to
manufacture a significant result that will not replicate.

Two rates are therefore reported, and they answer different questions:

- **task-level** (the headline). Each task gets one binary label: solved in a
  majority of its seeds. n = number of tasks. Seeds are spent reducing label noise,
  not inflating the sample. This is the rate that gets a confidence interval and
  the rate significance tests run on, because tasks are the independent units.

- **rollout-level** (diagnostic). Every (task, seed) rollout counted separately.
  Useful for seeing raw variance across seeds, and deliberately *not* used for
  inference: rollouts of the same task are correlated, so a CI computed over them
  would be too narrow and a p-value computed from them too small.

Run directories are named `<suite>__<model>__<condition>[__s<seed>]`; a directory
with no seed suffix is read as seed 0 so older result sets still load.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .stats import Comparison, compare, wilson_interval

_RUN_NAME = re.compile(r"^(?P<suite>[^_]+(?:_[^_]+)*?)__(?P<model>.+?)__(?P<cond>[a-z0-9_]+?)(?:__s(?P<seed>\d+))?$")


@dataclass
class ConditionSummary:
    """One experimental condition, pooled over however many seeds it was run with."""

    model: str
    condition: str
    seeds: list[int] = field(default_factory=list)

    # task_id -> list of per-seed outcomes
    per_task: dict[str, list[bool]] = field(default_factory=dict)
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    total_completion_tokens: int = 0
    avg_steps: float = 0.0

    # --- task-level (inferential) ---
    @property
    def task_labels(self) -> dict[str, bool]:
        """Majority vote across seeds. Ties (even seed counts) resolve to solved
        only if strictly more than half succeeded, so the label is conservative."""
        return {t: sum(v) * 2 > len(v) for t, v in self.per_task.items()}

    @property
    def num_tasks(self) -> int:
        return len(self.per_task)

    @property
    def num_resolved(self) -> int:
        return sum(self.task_labels.values())

    @property
    def solve_rate(self) -> float:
        return self.num_resolved / self.num_tasks if self.num_tasks else 0.0

    @property
    def solve_rate_ci(self) -> tuple[float, float]:
        return wilson_interval(self.num_resolved, self.num_tasks)

    # --- rollout-level (diagnostic only) ---
    @property
    def num_rollouts(self) -> int:
        return sum(len(v) for v in self.per_task.values())

    @property
    def rollout_rate(self) -> float:
        n = self.num_rollouts
        return sum(sum(v) for v in self.per_task.values()) / n if n else 0.0

    @property
    def unstable_tasks(self) -> list[str]:
        """Tasks whose outcome disagreed across seeds.

        A large set here is a warning about the *benchmark*, not the agent: it means
        single-seed numbers on this task set are largely reporting sampling noise.
        """
        return sorted(t for t, v in self.per_task.items() if 0 < sum(v) < len(v))


def load_conditions(output_dir: str = "results", suite: str | None = None) -> dict[tuple[str, str], ConditionSummary]:
    """Read every run under `output_dir`, grouped by (model, condition)."""
    base = Path(output_dir)
    if not base.exists():
        return {}

    grouped: dict[tuple[str, str], ConditionSummary] = {}
    for d in sorted(base.iterdir()):
        mp = d / "metrics.json"
        if not d.is_dir() or not mp.exists():
            continue
        m = json.loads(mp.read_text())
        parsed = _RUN_NAME.match(d.name)
        if not parsed:
            continue
        if suite and parsed["suite"] != suite:
            continue

        cond = parsed["cond"]
        seed = int(parsed["seed"] or m.get("seed", 0) or 0)
        model = m.get("model", parsed["model"])

        key = (model, cond)
        cs = grouped.setdefault(key, ConditionSummary(model=model, condition=cond))
        cs.seeds.append(seed)

        # Older runs predate per-task outcomes; they can still contribute a rate,
        # but not a paired comparison, so skip them rather than fake task ids.
        for task_id, resolved in (m.get("task_results") or {}).items():
            cs.per_task.setdefault(task_id, []).append(bool(resolved))
        for mode, count in (m.get("failure_breakdown") or {}).items():
            cs.failure_breakdown[mode] = cs.failure_breakdown.get(mode, 0) + count
        cs.total_completion_tokens += m.get("total_completion_tokens", 0) or 0
        cs.avg_steps = m.get("avg_steps", 0.0) or 0.0

    for cs in grouped.values():
        cs.seeds = sorted(set(cs.seeds))
    return grouped


def compare_to_baseline(
    conditions: dict[tuple[str, str], ConditionSummary],
) -> dict[tuple[str, str], Comparison]:
    """Paired McNemar of every condition against its own model's baseline.

    Each model is compared only to itself: a 1.5B ablation is meaningful against the
    1.5B baseline, not against a different model's.
    """
    out: dict[tuple[str, str], Comparison] = {}
    for (model, cond), cs in conditions.items():
        if cond == "baseline":
            continue
        base = conditions.get((model, "baseline"))
        if base is None or not base.per_task:
            continue
        out[(model, cond)] = compare(base.task_labels, cs.task_labels)
    return out


def coverage_warnings(conditions: dict[tuple[str, str], ConditionSummary]) -> list[str]:
    """Flag result sets that cannot support the claims someone will want to make."""
    from .stats import min_discordant_for_significance

    warnings: list[str] = []
    floor = min_discordant_for_significance()

    legacy = sorted(f"{m}/{c}" for (m, c), cs in conditions.items() if not cs.num_tasks)
    if legacy:
        warnings.append(
            f"{len(legacy)} run(s) predate per-task outcome logging and cannot be "
            f"compared or pooled — re-run them to include in the analysis: {', '.join(legacy[:4])}"
            + (" ..." if len(legacy) > 4 else "")
        )

    for (model, cond), cs in sorted(conditions.items()):
        if cs.num_tasks and cs.num_tasks < 2 * floor:
            warnings.append(
                f"{model}/{cond}: {cs.num_tasks} tasks — exact McNemar needs {floor} "
                f"one-directional flips to reach p<0.05, so no result on this task set "
                f"can be significant unless at least {floor}/{cs.num_tasks} tasks flip."
            )
            break  # one notice per sweep is enough; the task set is shared

    for (model, cond), cs in sorted(conditions.items()):
        if len(cs.seeds) == 1:
            warnings.append(
                f"{model}/{cond}: single seed — the rate carries no sampling variance."
            )
            break

    for (model, cond), cs in sorted(conditions.items()):
        unstable = cs.unstable_tasks
        if len(cs.seeds) > 1 and len(unstable) > cs.num_tasks * 0.25:
            warnings.append(
                f"{model}/{cond}: {len(unstable)}/{cs.num_tasks} tasks flipped across "
                f"seeds — single-seed numbers on this set are mostly noise."
            )
    return warnings
