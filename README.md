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

Ruff's `S` rules are a reimplementation of Bandit, so the two agree closely on
security findings. That near-duplication is what makes the measurement sharp
rather than what makes it redundant: `# noqa: S602` silences Ruff, but Bandit does
not honour Ruff's suppression syntax and keeps reporting. Measured:

| variant | ruff (shown) | bandit (held-out) |
|---|---|---|
| vulnerable | 2 | 3 |
| suppressed with `# noqa` | **0** | **3** |
| genuinely fixed | 1 | 2 |

Suppression collapses the shown analyser while the held-out twin holds steady. A
real fix reduces both. **The divergence between them is a direct measure of
gaming**, and `notebooks/00_smoke_test.ipynb` re-verifies this before any run.

Semgrep serves as a second held-out analyser with a genuinely different rule
engine, testing whether fixes generalise across engines rather than merely across
two implementations of the same rules.

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

## Status

**No results yet.** The only thing that exists is the smoke test, which converts
four assumptions into four measurements before any GPU time is spent: that each
model loads, what throughput it reaches under batch, that its native template
produces usable code, and that the analysers discriminate a fix from a
suppression.

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
