# Runbook

How to produce the numbers. Everything here runs on one machine against a local
Ollama server; nothing calls a paid API.

## 0. Before you run anything: check the power

The single most expensive mistake this project already made once was running a sweep
that could not possibly reach significance, then writing up the result as a finding.

```bash
make power                       # or: agenteval power --effect 0.2
agenteval power --tasks 28 --effect 0.33
```

The floor is structural: an exact McNemar test needs **at least 6 tasks to flip in the
same direction** before it can return p < 0.05, no matter how many seeds you run.
That gives a hard reading of what any given benchmark size can do:

| tasks | large effect (33% flip) | moderate effect (20% flip) |
|---|---|---|
| 12 | 18% | 12% |
| 20 | 69% | 34% |
| 28 | 94% | 50% |
| **38** (current) | **100%** | **81%** |

The original 12-task benchmark had an **18% chance** of detecting its own headline
effect. That is why the benchmark was expanded; it is not a cosmetic change.

At the current 38 tasks the sweep is well powered for both large and moderate effects.
A *small* effect (15% of tasks flipping) is still only ~53% — reaching 80% there would
take ~52 tasks. Report anything that small as a null with the interval shown rather than
narrating it as a trend.

**Seeds are not tasks.** Replicating a condition across seeds reduces label noise on
the tasks you have — it does not add independent evidence about an effect. Power comes
from tasks. Use seeds to stop one unlucky rollout becoming a published number, and
tasks to make the result mean something.

## 1. Setup

```bash
make install
make models        # pulls the three default tiers
```

### Cost

Nothing here is billable. Every model call goes to a local Ollama server, and the
SWE-bench provider drives local Docker. There are no API keys and no metered calls —
the cost is electricity and disk.

### Choosing model tiers

The default sweep uses `qwen2.5-coder` at **0.5b, 1.5b and 3b** (roughly 0.4 GB, 1 GB
and 2 GB on disk). Two reasons it is not one big model plus one small one:

- **Three points make a curve.** The claim this project is built to test — that
  scaffolding value falls as base-model capability rises — is a claim about a trend.
  Two tiers can only draw a line through two points; three can show it is monotone.
- **Headroom beats size.** In v1 the 7B solved 92% of tasks, so four of five ablations
  returned +0 for it. A model with no room to fall cannot show a lever's effect. Tiers
  are worth choosing for the headroom they leave, not for how strong they are.

Counter-intuitively, **weaker models cost more wall time here**, because they flail:

| v1 baseline | avg steps | avg wall time / task |
|---|---|---|
| `qwen2.5-coder:1.5b` | 15.5 | 12.5s |
| `qwen2.5-coder:7b` | 3.4 | 6.7s |

The 7B was slower per token but finished each task in about half the time, since it
took roughly a fifth of the steps. Do not budget on parameter count.

To use a different set:

```bash
make ablate MODEL_TIERS="qwen2.5-coder:1.5b qwen2.5-coder:7b"
```

## 2. Build and validate the benchmark

```bash
make benchmark      # writes benchmarks/local/
make validate       # must print "N/N tasks valid"
```

`make validate` enforces four properties per task, and a failure in any of them is a
benchmark bug rather than an agent result:

1. the buggy workspace **fails** the hidden oracle — the bug is real;
2. the stored gold patch **passes** the oracle — the task is solvable, not merely
   broken (an impossible task looks like a hard one in the results and quietly drags
   every condition toward zero);
3. the visible `test_basic.py` **fails** on the buggy code — otherwise `run_tests`
   tells the agent nothing and the tool ablation is measuring a tool with no signal;
4. nothing hangs — buggy code that loops forever turns every rollout into an
   `eval_timeout`.

Do not run a sweep until this is clean.

## 2b. Probe each tier before sweeping it

One baseline condition over all 38 tasks takes about 10 minutes and decides whether a
tier is worth an overnight run:

```bash
make baseline                                   # MODEL_MAIN
make baseline MODEL_MAIN=qwen2.5-coder:7b
```

**The headroom rule.** Before power, before seeds, ask how many tasks are *able* to
flip. An ablation that removes a capability can only break tasks the baseline solved,
and exact McNemar needs six one-directional flips for p<0.05. A tier that solves five
tasks can therefore never produce a significant negative result — not with more seeds,
not with more tasks. `make baseline` prints this warning itself when it applies.

| baseline solve rate | verdict |
|---|---|
| under ~16% (fewer than 6 solved) | floor: negative results cannot reach significance |
| ~30-70% | ideal — headroom in both directions |
| over ~84% (fewer than 6 unsolved) | ceiling: improvements cannot reach significance |

Measured on the 38-task benchmark, `max_steps=20`:

| tier | solve rate | dominant failure | read |
|---|---|---|---|
| `qwen2.5-coder:1.5b` | 13% (5/38) | `max_steps` 16, `no_edit` 10 | below the floor |
| `qwen2.5-coder:7b` | 47% (18/38) | `wrong_fix` 16 | ideal |

The failure mix says *why*, and points at different fixes. The 7B's `wrong_fix` majority
means it localizes and edits but reasons wrongly — the failure verification is meant to
catch, so the `run_tests` ablation has something real to move.

The 1.5B's budget failures turned out **not** to be a budget problem. Re-running it at
`--max-steps 30` produced a byte-identical outcome distribution (5 solved, 16 budget
failures, 10 `no_edit`, 7 `wrong_fix`) while spending 44% more tokens: at temperature 0
the first 20 steps are identical, and the extra 10 converted nothing. It was looping,
not running out of room — which is why the taxonomy separates `livelock` from
`max_steps`. It also solved 0 of the 26 multi-file tasks; all five solves were textbook
algorithms from the original single-file set.

Before assuming a budget failure means "raise the budget", check the split:

```bash
agenteval reclassify        # re-label saved trajectories, no model calls
```

`livelock` means a bigger budget will not help; `max_steps` means it might.

## 3. The sweep

```bash
make ablate-one      # one tier first — confirms the pipeline end to end
make ablate          # all three tiers
```

Expect hours, not minutes; plan on running it overnight. Per tier:

- 6 conditions x 3 seeds x 38 tasks ≈ 680 rollouts
- `best_of_3` spends up to 3x per *unsolved* task, so it dominates the tail — and it
  costs most on the weakest tier, which solves least
- v1 averaged 6–13s per task on 12 easy single-file tasks. The 38-task set is harder,
  so steps per task will rise; treat any extrapolation from v1 as a lower bound

Run `make ablate-one` before the full sweep. It produces a complete, analyzable result
for one tier in roughly a third of the time, and if something is misconfigured you find
out after a few hours rather than overnight.

Narrow further while iterating:

```bash
make ablate-fast                                     # 1 seed, 1 tier
agenteval run --name probe --subset config-layered-merge,csv-quoted-fields
```

`--subset` takes a comma-separated list of task ids, which is the fastest way to debug
the harness itself without paying for a full sweep.

### What the conditions mean

| condition | flips | compared against |
|---|---|---|
| `baseline` | — | — |
| `no_test_tool` | removes the `run_tests` tool | `baseline` |
| `no_repo_map` | removes the repo file listing from context | `baseline` |
| `windowed_history` | keeps only the last 8 turns | `baseline` |
| `sampling_control` | temperature 0.8, one attempt | `baseline` |
| `best_of_3` | three attempts, hidden tests pick the winner | `sampling_control` |
| `best_of_3_dev` | three attempts, visible tests pick the winner | `sampling_control` |

`best_of_3` is **pass@3**: the oracle chooses which attempt counts. It answers "could
the agent have solved this?" and is an upper bound no deployed system reaches, because
in production nothing tells you which of the three attempts was right. `best_of_3_dev`
uses the selection signal a real retry loop actually has — the agent's own visible
tests. Report the second as the value of retries; the gap between them is how much of
the gain rests on having a perfect verifier.

`best_of_3` is compared against `sampling_control`, not `baseline`. Multi-sampling
needs temperature > 0 to draw distinct rollouts, so it differs from the temperature-0
baseline in two fields at once. Comparing it to `baseline` would confound the retry
lever with the temperature change — which is how the earlier run reported a confident
"+0 from retries" that was really "the experiment never ran."

## 4. Read the results

```bash
make report          # pooled table: rates with CIs, paired deltas, p-values
make dashboard       # HTML report + refreshes the README results block
open results/dashboard.html
```

Every rate carries a 95% Wilson interval and every delta an exact McNemar p-value on
the paired task outcomes. The dashboard also lists *which* tasks each condition broke
or fixed — that per-task flip list is the mechanism behind the number and is usually
the most interesting thing in the report.

Watch for the warnings the report prints. `N/M tasks flipped across seeds` means
single-seed numbers on that set are mostly noise, and it is a reason to add seeds
before believing anything.

## 5. SWE-bench

```bash
make swebench        # provider=swebench, subset=verified_smoke
```

Requires Docker and the official SWE-bench harness; see [swebench.md](swebench.md)
for the Apple-Silicon setup and the curated arm64 subset. The same agent loop runs
unchanged — only the provider differs.

## 6. Writing it up

Two rules that come directly from what went wrong the first time:

- **Never quote a rate without its interval.** `42%` over 12 tasks has a 95% CI of
  19–68%. Quoting the point estimate alone implies a precision the run does not have.
- **Report nulls as nulls.** If an interval includes zero, say the condition showed no
  detectable effect at this sample size. Do not describe it as a trend, and do not
  reach for a mechanism to explain a difference the data cannot distinguish from zero.

`make report` prints "No condition reached significance" when that is the honest
summary, and the README block says so too. That output is a legitimate result — a
measured null on a benchmark whose power you can state is worth more than a
significant-looking number from a sweep that could not have concluded otherwise.
