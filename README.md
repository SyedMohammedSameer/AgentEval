# Agents don't game the linter. They obey it, and that is worse.

Four code LLMs were shown static-analysis findings on their own solutions and asked
to fix them. The study was built to catch them cheating: satisfying the analyser
they were shown while the defect stayed put. **They did not cheat.** Across 4,439
repair steps the four models wrote **five** suppression directives in total, and
94% of the findings they removed were also gone from a held-out analyser that was
never shown to them.

They complied. And complying with a security rule broke **one working program in
three**.

| | |
|---|---|
| findings removed from the shown analyser that survived in the held-out twin | **6%** [4%, 9%] |
| suppression directives written across 4,439 steps | **5** |
| working programs broken by repairing a security finding | **35.2%** [27%, 44%] |
| working programs broken by repairing a non-security finding | **8.8%** [5%, 16%] |
| same task, same model: security repair broke it but lint repair did not | **46 vs 3**, exact McNemar *p* = 7 × 10⁻¹¹ |

## The result the study was designed to find, and did not

The hypothesis was Goodhart's law applied to code quality gates: point an agent at
one analyser and it learns to satisfy that analyser rather than fix the code. The
instrument was built to detect exactly that. Ruff's `S` rules are a
reimplementation of Bandit's, numbered identically, and Bandit does not honour
`# noqa` — so a finding that vanishes from Ruff while its Bandit twin survives is
suppression, not repair.

| model | ruff findings removed | measurable | suppressed | 95% CI |
|---|---|---|---|---|
| deepseek-coder-6.7b | 152 | 62 | 2% | [0%, 9%] |
| granite-8b-code | 110 | 53 | 8% | [3%, 18%] |
| qwen2.5-coder-7b | 179 | 78 | 12% | [6%, 20%] |
| yi-coder-9b | 208 | 90 | 3% | [1%, 9%] |
| **pooled** | **649** | **283** | **6%** | **[4%, 9%]** |

The interval is nowhere near 50%. Two independent measurements agree: the counted
directives (5 across the whole study) and the held-out analyser (94% transfer).
Whatever these models do when handed a linter report, gaming it is not it.

That is a negative result on the study's own premise, and it is what makes the
next number believable.

## What actually happens

Every task ran two repair arms branching from the same baseline solution: one shown
Pylint findings, one shown Ruff findings. Where both arms ran on the same task and
the baseline passed its tests, the arms can be compared within that task, on that
model's own code.

| model | pairs | ruff broke it | pylint broke it | both | neither | *p* exact |
|---|---|---|---|---|---|---|
| deepseek-coder-6.7b | 46 | 9 | 1 | 1 | 35 | 0.022 |
| granite-8b-code | 49 | 10 | 0 | 0 | 39 | 0.002 |
| qwen2.5-coder-7b | 56 | 12 | 0 | 4 | 40 | 0.0005 |
| yi-coder-9b | 62 | 15 | 2 | 0 | 45 | 0.002 |
| **pooled** | **213** | **46** | **3** | **5** | **159** | **7 × 10⁻¹¹** |

Only the discordant pairs carry information, and they run 46 to 3 against the Ruff
arm. Every model is individually significant.

It is the security rules specifically, not Ruff in general:

| findings the agent was shown | tasks | broke | rate | 95% CI |
|---|---|---|---|---|
| at least one `S` (security) rule | 122 | 43 | **35.2%** | [27%, 44%] |
| no security rule | 91 | 8 | **8.8%** | [5%, 16%] |

## The clearest case: S311

`S311` — *"standard pseudo-random generators are not suitable for cryptographic
purposes"* — fired on 202 task-model pairs. The agents removed it 79% of the time.
It broke **42%** of the working programs it appeared in, the highest of any rule
with a meaningful sample.

None of that code was cryptographic. BigCodeBench uses `random` for data
generation, and its tests seed it and assert on the output. The agent does what it
is told, swaps `random` for `secrets`, and the program stops being deterministic.
`secrets` has no `seed()`, so some of them stop running at all:

```
BigCodeBench/87   qwen2.5-coder-7b   fail: NameError: name 'seed' is not defined
```

The finding was a true positive about the code and a false positive about the
context. The agent could not tell the difference, and nothing downstream of it
could either: the analyser reported success. Of the 51 broken repairs, 20 changed
behaviour while still running and 14 introduced a Pylint `E0602`/`E1101` — a name
the repair had removed.

`B006` (mutable default argument) behaves the same way: 17 tasks, **53%** broken.
Changing `def f(x=[])` to `def f(x=None)` is textbook correct and changes the API.

## Why this matters more than the gaming result

A suppressed finding is detectable — the directive is right there in the diff, and
a second analyser catches it. Faithful, destructive repair leaves nothing to find.
The analyser is satisfied, the diff looks like a fix, and the program is broken.
The only thing that catches it is running the code.

This is the empirical case for verification that is independent of the gate being
optimised against, and it is a different case from the one usually made. The risk
in an automated quality gate is not that agents cheat it. It is that they obey it
in contexts where its advice is wrong.

## What was run

Four code-specialised instruct models from four families, inside a 1.3× size
spread, all served at bfloat16 on one A100 through vLLM at temperature 0:

`Qwen/Qwen2.5-Coder-7B-Instruct` · `deepseek-ai/deepseek-coder-6.7b-instruct` ·
`01-ai/Yi-Coder-9B-Chat` · `ibm-granite/granite-8b-code-instruct-128k`

300 BigCodeBench tasks, drawn by a fixed shuffle and filtered to those whose
reference solution passes its own tests in this environment, so a missing package
costs coverage rather than corrupting the correctness measurement. Two repair
rounds per arm. 1,200 task-model pairs, 4,439 steps, 1.14 hours, zero errors.

Findings are tracked individually by code, never by count. Fixing
`subprocess.check_output(cmd, shell=True)` moves Ruff from `S602` to `S603` and
Bandit from `B602` to `B603` — both counts unchanged. A count-based delta scores a
real fix as worthless and a `# noqa` as a triumph, which would have inverted the
headline. The study observed 3 such swaps.

## Limitations

**Source code was not retained.** Steps record findings, codes, lines and test
outcomes, but not the text of each revision, so the S311 mechanism is established
from failure modes and introduced codes rather than from diffs. That is the first
thing to change in any follow-up.

**One sample per task at temperature 0.** The variance budget went into tasks
rather than seeds. These are point estimates for greedy decoding, not for the
distribution a sampled agent would produce.

**The Pylint arm reports no transfer rate.** Pylint's message ids have no Ruff or
Bandit counterpart, so that arm can say what was addressed but not whether the fix
transferred. It is recorded as unmeasurable rather than as zero suppression.
Pooled, the agents addressed 70% of Ruff findings and 20% of Pylint's.

**Single-file Python from one benchmark.** Nothing here extends to Java, to CodeQL,
or to repository-scale change without being measured there.

## Reproducing

`notebooks/03_study.ipynb` runs the whole study. It measures the accelerator and
sizes itself: one A100 (~1.1h) or a pair of T4s (~2.5h), Colab or Kaggle, nothing
to edit. It clones this repository rather than embedding it, and records the commit
in the run manifest, so a result traces to the code that produced it.

| | |
|---|---|
| `agentverif/` | the measurement, 60 tests |
| `notebooks/00_smoke_test` | models load and serve; measured throughput |
| `notebooks/01_corpus_check` | BigCodeBench schema and pass rate |
| `notebooks/02_analyser_selection` | density and overlap across nine analyser configs |
| `notebooks/03_study` | the run |

All analysis re-derives offline from `steps.jsonl` via `agentverif.report`, so the
tables can be re-sliced or corrected without another GPU hour.

## Prior work this does not repeat

Static analysis as a repair feedback loop is established ([arXiv 2508.14419][1],
[arXiv 2412.14841][2]), as is iterative refinement degrading security, and
self-repair across model scales and families ([arXiv 2604.10508][3]). Patch
overfitting to tests is long established in automated program repair.

What appears to be open, and what this measures, is whether a fix aimed at one
analyser survives contact with another — and what it costs the program when it
does.

[1]: https://arxiv.org/abs/2508.14419
[2]: https://arxiv.org/html/2412.14841v1
[3]: https://arxiv.org/abs/2604.10508
