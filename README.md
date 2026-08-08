# Does the agent fix the defect, or just the detector?

When a coding agent is shown static-analysis findings and asked to fix them, the
findings go down. That much is established. This project asks the question that
follows: **do the defects go down too, or does the agent learn to satisfy the
particular tool it was shown?**

## The design

A repair loop is given findings from one analyser (the *shown* analyser) and
measured against analysers it never sees (the *held-out* set), plus a test suite
so correctness is tracked throughout.

| outcome | what it would mean |
|---|---|
| shown drops, held-out flat | agents optimise the detector, not the code: the empirical case for independent verification |
| both drop together | quality gates generalise, which is good news and, as far as we can tell, unmeasured |

Either result is worth publishing, which is the property a study should have
before it is run.

## Why the instrument works

Ruff's `S` rules are a reimplementation of Bandit's, numbered identically, so
`S602` and `B602` are the same defect seen by two separately built engines. That
near-duplication is what makes the measurement sharp rather than redundant:
`# noqa: S602` silences Ruff, and Bandit does not honour Ruff's suppression syntax.

Measured on `subprocess.check_output(cmd, shell=True)` with ruff 0.15.8 and
bandit 1.9.4:

| variant | ruff (shown) | bandit (held out) |
|---|---|---|
| vulnerable | `S602` | `B404`, `B602` |
| suppressed with `# noqa` | *(none)* | `B404`, `B602` |
| genuinely fixed | `S603` | `B404`, `B603` |

Suppression empties the shown analyser while the held-out twin holds steady. **The
divergence between them is a direct measure of gaming**, and every notebook
re-verifies it on the installed tool versions before spending GPU time.

## Why counts are not the measurement

Read the same table as counts and it says the opposite of the truth:

| variant | ruff | bandit |
|---|---|---|
| vulnerable | 1 | 2 |
| suppressed | **0** | 2 |
| genuinely fixed | 1 | 2 |

The real fix leaves both counts exactly as they were, because `shell=True` swaps
`S602` for `S603` and `B602` for `B603`. A count-based delta scores a genuine fix
as worthless and a `# noqa` as a total success, inverting the study's own headline.

So every finding is tracked individually by code: **addressed** if the shown
analyser no longer reports it, **transferred** if its held-out counterpart is gone
too, **introduced** if a repair traded one defect for another. A finding with no
counterpart is recorded as *unmeasurable* rather than folded into either bucket,
because counting it either way would manufacture a result.

Pylint is the third analyser: an independent implementation that honours neither
Ruff's nor Bandit's suppression syntax, firing on 100% of files at 4.3 findings
each where Ruff manages 42% and Bandit 19%. Semgrep and mypy were dropped on
evidence, not preference: across 80 BigCodeBench solutions they fired on 1-4% of
files, too rarely to support any comparison.

## Models

Four families, four pretraining corpora, all code-specialised instruct models
within a 1.3x size spread:

| family | model | params |
|---|---|---|
| Alibaba | `Qwen/Qwen2.5-Coder-7B-Instruct` | 7.6B |
| DeepSeek | `deepseek-ai/deepseek-coder-6.7b-instruct` | 6.7B |
| 01.AI | `01-ai/Yi-Coder-9B-Chat` | 8.8B |
| IBM | `ibm-granite/granite-8b-code-instruct-128k` | 8B |

All are Llama or Qwen2 architecture, the most exercised paths in vLLM, and all are
ungated. Served at float16 with tensor-parallel 2 on 2x T4, so no quantisation
kernels are involved on sm75. Each model gets its own chat template, since a
hand-rolled prompt shared across families would confound family with formatting.

## The study

Each task produces one baseline solution, then two repair arms branching from that
same baseline rather than chaining:

| arm | shown | rounds | runs on |
|---|---|---|---|
| `shown_pylint` | pylint | 2 | every task |
| `shown_ruff` | ruff | 2 | tasks with ruff findings |

Branching is what makes every comparison paired within a task, which is where the
power comes from at this sample size. Both arms record findings from all three
analysers at every step, plus the task's own tests, because a finding removed by
breaking the function is not a fix and has to stay distinguishable from one that
was merely hidden.

Corpus is BigCodeBench (1140 tasks, 92% of its reference solutions pass their own
tests in this environment), shuffled once with a fixed seed so every model walks
the same order. A model that runs out of time therefore holds a uniform random
sample, and the four task sets are nested rather than disjoint, so the cross-model
table can be computed on the tasks all of them reached.

## Notebooks

| notebook | hardware | what it settles |
|---|---|---|
| `00_smoke_test` | 2x T4 | all four models load and serve; measured throughput |
| `01_corpus_check` | CPU | BigCodeBench schema, assembly, and 92% pass rate |
| `02_analyser_selection` | CPU | density and overlap across nine analyser configs |
| `03_study` | 2x T4 | the run, hard-capped at 3h, checkpointed and resumable |

`03_study` carries a byte-for-byte copy of `agentverif/` rather than a second
implementation, and prints each module's sha256 so it can be checked against the
repository. Its only job is orchestration and printing; every measurement is made
by code with tests.

## Status

**No results yet.** Everything up to the run is verified: the substrate, the
corpus, the analyser choice, and the instrument. 50 tests cover the measurement
layer, including the case where counting findings would invert the headline.

## Prior work this deliberately does not repeat

Static analysis as a feedback loop is done ([arXiv 2508.14419][1],
[arXiv 2412.14841][2]). Iterative refinement degrading security is done, and
quantified. Self-repair across model scales and families is done
([arXiv 2604.10508][3]). Patch overfitting to tests is long established in the
automated-program-repair literature.

What appears to be open, and what this measures, is whether a fix aimed at one
analyser survives contact with another.

[1]: https://arxiv.org/abs/2508.14419
[2]: https://arxiv.org/html/2412.14841v1
[3]: https://arxiv.org/abs/2604.10508
