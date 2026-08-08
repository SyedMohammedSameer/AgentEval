# My coding-agent eval had an 18% chance of finding its own result

A few weeks ago I built a harness to measure what actually makes an LLM coding agent
work. It ran a ReAct agent against a benchmark of Python bug-fix tasks, logged full
trajectories, sorted failures into a taxonomy, and ran controlled ablations — flip one
design choice, measure the change in solve rate.

It produced a clean headline: **the `run_tests` tool is worth +33 points of solve rate
to a 1.5B model and nothing to a 7B.** Scaffolding value is inversely proportional to
base-model capability. Good story, useful implication: the tool you'd cut from your
strongest model might be load-bearing on the cheap one you actually deploy.

Then I checked whether the experiment could have detected that.

It couldn't. Here is what I found, and what the numbers look like after a rebuild.

## The power problem

The benchmark had 12 tasks. Solve rates were 5/12 and 1/12.

Ablation conditions run on the *same* tasks, so the right test is paired — McNemar's,
which looks only at tasks where two conditions disagree. And exact McNemar has a hard
floor: it cannot return p < 0.05 until **six tasks flip in the same direction**
(2 × 0.5⁶ = 0.031). Fewer than six, and no p-value below 0.05 is reachable. Ever.

A 12-task benchmark where a large effect moves four tasks is arithmetically incapable
of significance. Simulating the effect size I'd reported:

| tasks | power to detect it |
|---|---|
| **12** | **18%** |
| 20 | 69% |
| 38 | 100% |

My headline finding had an 18% chance of being detectable by the experiment that
produced it. It wasn't evidence. It was a coin flip that landed suggestively.

Two other things were broken, both found by writing a validator that checks the
benchmark rather than the agent:

- **Five of twelve tasks had visible tests that passed on the buggy code.** The agent
  could run `run_tests`, see green, and learn nothing. The tool-availability ablation
  was partly measuring a tool with nothing to report — which is the headline.
- **Best-of-N never ran.** Three attempts at temperature 0 draw three identical
  rollouts. The reported "+0 from retries" was a config bug reported as a null result.

## The rebuild

Briefly, since the point is the results:

- **38 tasks, up from 12.** 26 are multi-file: the bug lives at the seam between
  modules — config layering, cache TTL and eviction, cursor pagination, semver
  precedence, sliding-window rate limiting, dependency cycles, permission inheritance.
  The originals were textbook algorithms present verbatim in any code model's
  pretraining data, so a "solve" was partly recall.
- **Every task ships a gold patch** the agent never sees, and the validator requires it
  to pass. An unsolvable task doesn't look broken in results — it looks *hard*, and
  drags every condition toward zero equally.
- **Wilson intervals and paired McNemar everywhere.** No rate prints without its
  interval; no delta prints without its p-value.
- **Best-of-N gets a control.** Multi-sampling needs temperature > 0, so it differs
  from a temperature-0 baseline in two ways at once. A `sampling_control` condition
  (same temperature, one attempt) isolates the retry lever.
- **Three seeds per condition**, pooled by majority vote at the task level. Seeds
  reduce label noise; they are not extra tasks and don't add power.

Everything runs locally against Ollama. Total API spend: $0.

## What replicated

Nothing.

`qwen2.5-coder:7b`, 38 tasks, 3 seeds:

| condition | solve rate (95% CI) | Δ vs reference | p |
|---|---|---|---|
| baseline | 47% (18/38) [32–63] | — | — |
| − `run_tests` tool | 42% (16/38) [28–58] | −5 [−18, +8] | 0.688 |
| − repo map | 39% (15/38) [26–55] | −8 [−24, +8] | 0.549 |
| windowed history | 45% (17/38) [30–60] | −3 [−8, +0] | 1.000 |
| sampling control (T=0.8) | 39% (15/38) [26–55] | −8 [−24, +8] | 0.508 |
| **best-of-3 (pass@3)** | **79% (30/38) [64–89]** | **+39 [+24, +55]** | **<0.001** |

The `run_tests` result — my original headline — is **−5 points, p = 0.69**. A null. The
context levers are nulls too, and at 38 tasks the sweep has 81% power for a
moderate-sized effect, so these nulls are informative rather than merely inconclusive.

The 1.5B tier came back floored: 13% baseline, 5 tasks solved. With only 5 solves, an
ablation that removes a capability can break at most 5 tasks — under the 6 needed for
significance. The harness now prints that warning after a ten-minute probe, before you
spend a night on a sweep that cannot conclude.

## The one thing that worked: retries

Best-of-3 is the only significant result in the study, and it's large: **+39 points**
over its temperature-matched control.

It's also mechanically boring in the best way. Single-attempt success was 15/38 =
39.5%. If three attempts are independent draws, you'd predict
`1 − (1 − 0.395)³` = **77.8%**. Observed: **78.9%**. The attempts behave as
near-independent samples, and the gain is exactly what independent sampling buys.

**The caveat, stated plainly:** this is pass@3 — the hidden tests decide which of the
three attempts counts. It answers "could the agent have solved this?", not "would a
deployed system have shipped the right patch?" In production nothing tells you which
attempt was correct; you'd need a selection signal, like running the visible tests and
keeping the first attempt that passes. The deployable number is lower than +39, and the
gap between them is the portion of the gain that depends on having a perfect verifier.

There's a second-order finding hiding in that table. Raising temperature to 0.8 *cost*
8 points on a single attempt (47% → 39%) and then bought 39 back across three. Sampling
diversity is a liability once and an asset three times.

## Extra step budget bought nothing

The 1.5B's dominant failure was hitting the step limit — 16 of 38 tasks. The obvious
read is "it needed more room." So I re-ran it with the budget raised 20 → 30.

| | max_steps = 20 | max_steps = 30 |
|---|---|---|
| solved | 5 | **5** |
| budget failures | 16 | **16** |
| no edit | 10 | **10** |
| wrong fix | 7 | **7** |
| completion tokens | 68,118 | **97,967** |

Byte-identical outcomes, 44% more tokens. At temperature 0 the first 20 steps are the
same, and the extra 10 converted nothing. Those runs weren't running out of room — they
were cycling.

That's a flaw in the taxonomy, not just the model. A `max_steps` bucket documented as
"ran out of budget mid-solve" points at *raise the budget*, which is measurably the
wrong fix for these runs. The taxonomy now separates **livelock** (the budget went on
repeating earlier actions — a bigger budget won't help) from **max_steps** (still
taking new actions when it ran out — it might).

The same tier also solved **0 of the 26 multi-file tasks.** All five of its solves were
textbook algorithms from the original single-file set. Make of that what you will about
what small-model benchmark scores measure.

## 61% of tasks flipped between seeds

The harness warns when a condition's tasks disagree across seeds. At temperature 0.8:

> `sampling_control`: 23/38 tasks flipped across seeds
> `best_of_3`: 16/38 tasks flipped across seeds

Roughly **three in five tasks returned a different answer depending on the seed.** Any
single-run number on this benchmark at that temperature is mostly noise — which is
also, incidentally, why best-of-N works so well here. It's the same variance, harvested
instead of suffered.

## What I'd tell my past self

**Compute the power before the run, not after.** It takes seconds and it's the
difference between an experiment and an anecdote. If a large effect moves four tasks
and your test needs six, no amount of careful writing fixes that.

**Validate the benchmark, not just the agent.** Five of my twelve tasks had visible
tests that passed on buggy code. I'd have kept publishing that number indefinitely.

**A null with a stated interval beats a significant-looking number from an
underpowered sweep.** Most of my results are nulls now. They're worth more than the
+33 was.

**Check what your metric is selecting on.** The difference between pass@k and a
deployable retry loop is one line in the runner and a factor I'd have shipped without
noticing.

The harness is [on GitHub](https://github.com/SyedMohammedSameer/AgentEval). It runs
entirely on a laptop against Ollama — 38 tasks, six ablation conditions, confidence
intervals, paired significance tests, and a power calculator that tells you whether the
run you're about to start could conclude anything.
