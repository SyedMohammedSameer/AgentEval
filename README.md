# agenteval — an evaluation harness for LLM coding agents

A benchmark-agnostic harness that runs an LLM coding agent against software-engineering
tasks, measures **solve rate with confidence intervals**, records full **trajectories**,
classifies **failure modes**, and runs controlled **ablations** to attribute solve-rate
changes to specific agent design choices (context construction, tool availability,
retry strategy).

Everything runs locally against an open-weights model (Qwen2.5-Coder via Ollama) — **no API
or GPU spend**. The same code targets any OpenAI-compatible endpoint by changing one config
object, and a SWE-bench provider plugs into the identical agent loop.

## Why this exists

Raw pass/fail hides *why* an agent fails. This harness separates:

| Failure mode | What it means | The fix it points to |
|---|---|---|
| `no_edit` | agent never edited a file | localization / confidence |
| `patch_apply_failed` | diff was malformed | edit formatting |
| `wrong_fix` | patch applied, tests still fail | reasoning / correctness |
| `max_steps` | ran out of budget mid-solve | efficiency / planning |
| `protocol_violation` | couldn't emit a valid action | instruction following |
| `eval_timeout` | patch hung the test suite | introduced regression |

Turning a solve-rate number into a *failure distribution* is what makes the results
actionable. Turning it into a distribution **with an error bar** is what makes it
trustworthy — see [Measuring honestly](#measuring-honestly) below.

## Architecture

```
provider (local | swebench)      # loads tasks, builds sandboxes, scores patches
        │
        ▼
   Environment  ◄──────  Agent (ReAct loop)  ◄──────  LLMClient (OpenAI-compatible)
   exec / diff            think → act → observe        local Ollama or any API
        │
        ▼
   Trajectory ──► failure_taxonomy ──► metrics ──► stats ──► aggregate ──► dashboard
```

- **Benchmark-agnostic:** the agent only sees `exec` + patch operations, so the local
  benchmark and SWE-bench share one agent implementation.
- **Ablation-ready:** every behavioral knob lives on `AgentConfig`; an experiment is a
  single field flip.
- **Reproducible:** each run persists its config, per-task trajectories, and metrics,
  and sampling is seeded per (run, task, attempt).

## Quickstart

```bash
# 1. install (dev deps only — no Docker/SWE-bench needed)
make install

# 2. get a local model
ollama pull qwen2.5-coder:7b

# 3. build the benchmark and check it is sound
make benchmark
make validate            # must print "38/38 tasks valid"

# 4. check the sweep can actually detect what you're looking for
make power

# 5. run the sweep and render the report
make ablate              # 6 conditions x 3 seeds x 2 models — takes hours
make dashboard
open results/dashboard.html
```

Full procedure, including cost and what to check at each step, is in
[docs/runbook.md](docs/runbook.md).

## Measuring honestly

Most of the machinery here exists because the first version of this project reported a
result its sample size could not support. Three things now prevent that:

**Confidence intervals everywhere.** Solve rate is a binomial proportion over a few
dozen tasks, so it gets a 95% Wilson interval — an interval that stays inside [0,1] and
holds coverage at small n, unlike the textbook normal approximation. No rate is printed
without it. For scale: `42%` over 12 tasks has a 95% CI of **19–68%**.

**Paired significance tests.** Ablation conditions run the *same tasks*, so comparing
them is a paired design. The harness uses an exact McNemar test on the tasks where two
conditions disagree, and reports which tasks each condition broke or fixed.

**Power analysis before the run, not after.** Exact McNemar cannot return p < 0.05
until at least **six tasks flip in the same direction**, which puts a hard floor under
how small a benchmark can be and still conclude anything:

| tasks | large effect (33% flip) | moderate effect (20% flip) |
|---|---|---|
| 12 | 18% | 12% |
| 20 | 69% | 34% |
| 28 | 94% | 50% |
| **38** | **100%** | **81%** |

`agenteval power` prints this for any effect size. The original 12-task benchmark had
an **18% chance** of detecting its own headline effect — which is why the benchmark was
expanded to 38 tasks, the point where a moderate effect (the plausible size of the
context-construction levers) clears 80% power rather than coming back as an
uninformative null.

Seeds are not a substitute for tasks. Replicating a condition across seeds reduces
label noise on the tasks you have; only more tasks add independent evidence about an
effect. The harness therefore computes intervals and tests over **tasks** (a task counts
as solved if it succeeded in a majority of seeds) and treats rollout-level rates as
diagnostic only.

## Results

<!-- RESULTS:START -->

**Status: re-run pending.** The published v1 numbers have been withdrawn rather than
updated, because three independent problems made them uninterpretable:

1. **Underpowered.** 12 tasks gave an 18% chance of detecting the headline effect. The
   reported `-33 pts` for removing `run_tests` could not have reached significance at
   that sample size under any pairing of the outcomes (best case p=0.125).
2. **Five tasks had uninformative visible tests.** On `balanced-brackets`,
   `caesar-cipher-wrap`, `dedup-preserve-order`, `flatten-deep` and `merge-intervals`
   the visible `test_basic.py` *passed on the buggy code*, so `run_tests` returned
   green regardless. The tool-availability ablation was partly measuring a tool with
   nothing to report.
3. **Best-of-N never ran.** Three attempts at temperature 0 draw three identical
   rollouts, so the reported "+0 from retries" was a config bug, not a null result.

The v1 run directories are preserved under `results/legacy-v1/` and are excluded from
analysis. Re-running `make ablate` on the 38-task benchmark regenerates this block with
intervals and p-values.

<!-- RESULTS:END -->

Method and the reasoning behind each fix: [docs/findings.md](docs/findings.md).
Interactive report at `results/dashboard.html` (`make dashboard`).

## The local benchmark

Thirty-eight self-contained Python bug-fix tasks (`benchmarks/local/`), each with a
genuine bug, a *visible* basic test the agent can run, and a *hidden* oracle used only
for scoring — mirroring "you have some tests, CI has more."

- **12 single-file algorithm tasks** (slugify, RLE, binary search, …).
- **26 multi-file application tasks** — a small package where the bug lives at the seam
  between modules: config layering, cache eviction and TTL, cursor pagination, semver
  precedence, sliding-window rate limiting, CSV quoting, dependency cycles, route
  precedence, permission inheritance, batch flushing, schema validation, state-machine
  guards, predicate composition, diff hunk offsets, priority-queue tie-breaking, query
  encoding, markdown list nesting, stock reservation, circuit-breaker reset, feature-flag
  overrides, log retention. Localization is a real step, and these have no canonical
  published solution to recall.

Authored by `scripts/build_local_benchmark.py` and checked by
`scripts/validate_benchmark.py`, which enforces four properties per task:

1. the buggy workspace **fails** the hidden oracle — the bug is real;
2. the stored gold patch **passes** the oracle — the task is *solvable*, not merely
   broken (an impossible task scores zero under every condition and silently drags
   every measured effect toward zero);
3. the visible test **fails** on the buggy code — otherwise `run_tests` gives the agent
   no signal;
4. nothing hangs.

Gold patches live in `benchmarks/local/<task>/solution/`, which is never copied into an
agent's environment.

## SWE-bench

`--provider swebench` runs the same agent against SWE-bench Verified using the official
Docker-based evaluation. See [docs/swebench.md](docs/swebench.md) for the Apple-Silicon
setup and curated arm64 smoke subset.

## License

MIT
