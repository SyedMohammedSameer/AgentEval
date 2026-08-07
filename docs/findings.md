# Findings

## Status

The v1 results have been **withdrawn**, not revised. This document explains what they
claimed, why the claims did not hold, and what the harness now does so the re-run
produces something publishable. Run directories from v1 are preserved under
`results/legacy-v1/` and excluded from analysis.

The short version: the numbers were probably pointing at something real, but the
experiment could not have demonstrated it, and two of the four conditions were measuring
something other than what they were labelled.

## What v1 claimed

Twelve single-file Python bug-fix tasks, two model tiers (Qwen2.5-Coder 1.5B and 7B via
Ollama, temperature 0), one seed per condition.

| condition | 1.5B | 7B |
|---|---|---|
| baseline | 42% (5/12) | 92% (11/12) |
| − run_tests tool | 8% (−33) | 92% (+0) |
| − repo map | 58% (+17) | 92% (+0) |
| windowed history | 42% (+0) | 92% (+0) |
| best-of-3 | 42% (+0) | 92% (+0) |

The headline was "scaffolding value is inversely proportional to base-model capability",
resting on the −33 point drop for the 1.5B and +0 for the 7B.

## What was wrong

### 1. The sample could not support any of it

With 12 tasks, a 42% solve rate has a 95% Wilson interval of **19–68%**. The `+17` for
removing the repo map is a two-task swing well inside that.

Worse, the headline effect could not have reached significance either. Conditions run on
the same tasks, so the correct test is paired (exact McNemar). Per-task outcomes were not
recorded in v1, but the marginals (5/12 vs 1/12) bound the result: across every pairing
consistent with them, the best achievable p-value is **0.125**.

This is structural, not bad luck. Exact McNemar needs at least **six tasks to flip in the
same direction** before it can return p < 0.05 — `2 × 0.5⁶ = 0.031`. A 12-task benchmark
where a large effect moves ~4 tasks is arithmetically incapable of significance.

Simulating the observed effect size gives the power directly:

| tasks | power at a large effect (33% of tasks flip) |
|---|---|
| 12 | **18%** |
| 20 | 69% |
| 28 | 94% |
| 40 | 100% |

**v1 had an 18% chance of detecting its own headline finding.** It is not evidence for
the claim; it is a coin flip that landed suggestively.

### 2. The 7B was at a ceiling

92% on 12 tasks leaves one solvable task of headroom. Four of five ablations returned +0
for the 7B, which was read as "scaffolding doesn't help strong models". A lever that
cannot move a score because the score is pinned has not been measured — it has been
hidden. The "inversely proportional to capability" story needs a task set where both
tiers have room to move in both directions.

### 3. Five tasks gave the `run_tests` tool nothing to report

The new validator checks that each task's *visible* test fails on the buggy code. Five of
the original twelve failed that check: `balanced-brackets`, `caesar-cipher-wrap`,
`dedup-preserve-order`, `flatten-deep`, `merge-intervals`. On those, `test_basic.py`
passed on the buggy code, so an agent running `run_tests` saw green and learned nothing.

This lands squarely on the headline. The `no_test_tool` ablation removes a tool that was
informative on only 7 of 12 tasks, so the measured effect is a blend of "verification
matters" and "the visible tests were weak" — with no way to separate them after the fact.

### 4. Best-of-3 never ran

Three attempts at temperature 0 draw three *identical* rollouts. The condition spent 3×
the tokens and reported +0. That is not a null result about retries; the experiment
never happened.

It also could not have been fixed by simply raising the temperature, because then
`best_of_3` would differ from the temperature-0 baseline in two fields at once, and any
delta would confound retries with sampling temperature.

## What changed

**Uncertainty is now structural, not editorial.** `stats.py` provides Wilson intervals,
exact McNemar, a paired task-level bootstrap for delta CIs, and power/sample-size
helpers. `metrics.py` records per-task outcomes, without which no paired test is possible.
Every reporting surface — CLI table, HTML dashboard, README block — prints the interval
and the p-value alongside the rate, so a bare percentage cannot be copied out of them.

**The benchmark went from 12 to 28 tasks**, and 16 of the new ones are multi-file
application-shaped bugs (config layering, cache TTL and eviction, cursor pagination,
semver precedence, sliding-window rate limiting, CSV quoting, dependency cycles, route
precedence, permission inheritance, batch flushing, schema validation). Two reasons:
power (18% → 94% for a large effect) and construct validity — the original tasks are
textbook algorithms present verbatim in any code model's pretraining data, so a solve was
partly recall. Bugs that live at the seam between two modules make localization a real
step.

**Every task now ships a gold patch** under `benchmarks/local/<task>/solution/`, never
visible to the agent. `make validate` requires the gold patch to pass the oracle, which
proves each task is solvable rather than merely broken. An unsolvable task does not look
broken in the results — it looks hard, and it drags every condition toward zero equally.

**Best-of-N gets a control.** `sampling_control` runs one attempt at the same temperature
as `best_of_3`, and the retry lever is measured as `best_of_3` vs `sampling_control`.
Sampling seeds are derived per (run seed, task, attempt), so attempts genuinely differ
while runs stay reproducible. Configs that cannot produce a valid result — multi-sampling
at temperature 0, a history window shorter than one think/act/observe cycle — are now
flagged before the run starts.

**Conditions are replicated across seeds**, with a task counted as solved if it succeeded
in a majority of its seeds. Seeds reduce label noise; they do not inflate n. Tests and
intervals are computed over tasks, and the report warns when tasks flip across seeds
often enough that single-seed numbers would be mostly noise.

## What the re-run can and cannot settle

At 28 tasks the sweep has 94% power for a large effect (a third of tasks flipping) and
about 50% for a moderate one (a fifth). So:

- A large `run_tests` effect on the small model, if real, will be detected and can be
  stated with an interval.
- A moderate effect — plausibly the size of the context-construction levers — is still a
  coin flip. Reaching 80% power there needs ~38 tasks. Report those as nulls with the
  interval shown, and do not narrate a mechanism for a difference the data cannot
  distinguish from zero.
- Anything about the 7B depends on whether the multi-file tasks pull it off the ceiling.
  If it lands above ~90% again, the cross-tier comparison is still not measurable and the
  honest move is to say so and pick a harder task set, not to publish the +0s as a
  finding.

The failure-taxonomy mechanism from v1 — that removing verification more than doubled
`max_steps` non-termination, so the agent could not tell when to stop — is the most
interesting observation in the project and is worth re-checking directly, since it is a
claim about the *shape* of failure that does not depend on the solve-rate delta reaching
significance.
