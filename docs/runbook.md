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

| tasks | power at a large effect (33% of tasks flip) |
|---|---|
| 12 | 18% |
| 20 | 69% |
| 28 | 94% |
| 40 | 100% |

The original 12-task benchmark had an **18% chance** of detecting its own headline
effect. That is why the benchmark was expanded; it is not a cosmetic change.

At the current 28 tasks the sweep has 94% power for a large effect but only ~50% for a
moderate one (a fifth of tasks flipping) — reaching 80% there needs about 38 tasks. Plan
on reporting moderate-sized effects as nulls with the interval shown, or add tasks first
if that is the effect size you care about.

**Seeds are not tasks.** Replicating a condition across seeds reduces label noise on
the tasks you have — it does not add independent evidence about an effect. Power comes
from tasks. Use seeds to stop one unlucky rollout becoming a published number, and
tasks to make the result mean something.

## 1. Setup

```bash
make install
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:7b
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

## 3. The sweep

```bash
make ablate          # 6 conditions x 3 seeds x 2 models
```

Expect this to take hours, not minutes — plan on running it overnight. The rough
shape on an M-series laptop, per model:

- 6 conditions x 3 seeds x ~28 tasks ≈ 500 rollouts
- `best_of_3` costs up to 3x per unsolved task, so it dominates the tail
- the 7B is several times slower per step than the 1.5B

Narrow it while iterating:

```bash
make ablate-fast                                     # 1 seed, small model only
agenteval run --name probe --subset config-layered-merge,csv-quoted-fields
```

`--subset` takes a comma-separated list of task ids, which is the fastest way to
debug the harness itself without paying for a full sweep.

### What the conditions mean

| condition | flips | compared against |
|---|---|---|
| `baseline` | — | — |
| `no_test_tool` | removes the `run_tests` tool | `baseline` |
| `no_repo_map` | removes the repo file listing from context | `baseline` |
| `windowed_history` | keeps only the last 8 turns | `baseline` |
| `sampling_control` | temperature 0.8, one attempt | `baseline` |
| `best_of_3` | temperature 0.8, three attempts | `sampling_control` |

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
