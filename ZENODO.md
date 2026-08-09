# Zenodo submission — field by field

Everything to paste is below, in the order the form asks for it. Only `paper.pdf`
gets uploaded.

---

## Files

Upload **one file**: `paper.pdf`.

The data and code are not uploaded here; the paper points to the GitHub
repository for both, and the raw run (`steps.jsonl`) is now committed there so
that link resolves.

> Zenodo will not let you add, remove or change files after publishing. If you
> later decide to attach the data too, that means publishing a new version, which
> gets its own DOI under the same concept DOI.

---

## Basic information

**Digital Object Identifier** → select **"No, I need one"**.
Your form currently has *"Yes, I already have one"* selected, which will block
submission because the box is empty. You want Zenodo to mint one.

**Resource type** → `Publication` › **`Preprint`**

**Title**
```
Agents Don't Game the Linter: Measuring Whether LLM Repair Satisfies the Analyser or Fixes the Defect
```

**Publication date** → `2026-08-09` (already filled)

**Authors/Creators** → Add author: your name, and add your ORCID if you have one.
An ORCID is worth the two minutes — it makes the record findable under you rather
than under a name string.

---

## Description

Plain text. Paste it in; the editor keeps the paragraph breaks.

```
Four code-specialised LLMs were shown static-analysis findings on their own solutions and asked to fix them. The study was designed to catch Goodharting: satisfying the analyser that was shown while the defect stayed put. It did not happen. Across 4,439 repair steps the models wrote five suppression directives in total, and 94% of the findings they removed were also gone from a held-out analyser they never saw (suppression rate 6%, 95% CI [4%, 9%]).

They complied instead, and complying was expensive. Each task ran two repair arms branching from the same baseline solution: one shown Pylint findings, one shown Ruff findings. Restricted to tasks where both arms ran and the baseline passed its own tests, the Ruff arm broke the program where the Pylint arm did not on 46 occasions against 3 the other way (exact McNemar, p = 7 × 10⁻¹¹, 213 pairs, every model individually significant).

That result is one rule. Ruff's S311 ("pseudo-random generators are not suitable for cryptographic purposes") broke 41.8% [32%, 52%] of the working programs it appeared in, against 8.8% [5%, 16%] where no security rule was shown. Remove every S311 task and the paired comparison falls to 10 versus 3, p = 0.09. This is therefore not evidence that security rules as a class are dangerous in a repair loop; it is evidence that S311 is, and that one rule was enough to make an entire ruleset look four times more destructive than another.

None of the affected code was cryptographic. BigCodeBench uses random for data generation and seeds it in the tests, so the agent swaps in secrets, determinism is lost, and since secrets has no seed() some programs stop running at all: a true positive about the code and a false positive about the context, with the analyser reporting success either way. A suppressed finding leaves a directive in the diff; faithful destructive repair leaves nothing to find. That is an empirical case for verification independent of the gate being optimised against, and a different case from the one usually made.

Method: four models from four families (Qwen2.5-Coder-7B-Instruct, deepseek-coder-6.7b-instruct, Yi-Coder-9B-Chat, granite-8b-code-instruct-128k), bfloat16 on one A100 via vLLM at temperature 0; 300 BigCodeBench tasks filtered to those whose reference solution passes its own tests in the run environment; two repair rounds per arm; 4,439 steps.

Code and the complete raw record: https://github.com/SyedMohammedSameer/AgentEval
```

**Licenses** → keep **Creative Commons Attribution 4.0 International** (already
set). That covers the paper; the code in the repository is MIT.

---

## Recommended information

**Keywords and subjects** — add these one at a time:

```
large language models
code generation
static analysis
automated program repair
software quality
AI code review
Goodhart's law
empirical software engineering
BigCodeBench
LLM evaluation
```

**Languages** → `eng`

**Dates** → leave the extra Dates block empty, or delete the blank row. It has a
required Type field and an empty row can block submission.

**Version** → `1.0.0`

**Publisher** → `Zenodo` (already filled)

---

## Related works

Add one row:

| field | value |
|---|---|
| Relation | `Is supplemented by` |
| Identifier | `https://github.com/SyedMohammedSameer/AgentEval` |
| Scheme | `URL` |
| Resource type | `Software` |

Add a second row for the benchmark:

| field | value |
|---|---|
| Relation | `Is derived from` |
| Identifier | `10.48550/arXiv.2406.15877` |
| Scheme | `DOI` |
| Resource type | `Dataset` |

---

## References

Add each as a Reference string:

```
Zheng, T. et al. BigCodeBench: Benchmarking Code Generation with Diverse Function Calls and Complex Instructions. arXiv:2406.15877 (2024).
```
```
Static analysis feedback in LLM repair loops. arXiv:2508.14419.
```
```
Iterative refinement and code security. arXiv:2412.14841.
```
```
Self-repair across model scales and families. arXiv:2604.10508.
```

> Check those last three arXiv numbers against what you actually cite before
> publishing — they came from the earlier literature pass and I have not re-fetched
> them. A wrong reference in a DOI'd record is not fixable without a new version.

---

## Leave empty

Alternate identifiers · Funding/Awards · Journal · Imprint · Thesis · Conference ·
Domain specific fields · Contributors.

---

## Before you press Publish

1. **Preview** — check the description renders as paragraphs, not raw HTML.
2. **Visibility** — Public (already set).
3. **Files are frozen after publishing.** Confirm `paper.pdf` is attached.
4. **Save draft** first. Publishing mints the DOI and cannot be undone.
