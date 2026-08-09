# Zenodo submission — field by field

Everything to paste is below, in the order the form asks for it. Files to upload
are in `zenodo/`.

---

## Files

Upload all six. Drag the whole `zenodo/` contents in at once.

| file | what it is | size |
|---|---|---|
| `steps.jsonl` | the raw record: every step of every arm, findings by tool and code, test outcome, directives, tokens | 2.1 MB |
| `summary.json` | every table in the paper, plus the per-finding fates behind them | 2.4 MB |
| `run_manifest.json` | models, seed, budgets, analyser and vLLM versions, the git commit, the 300 task ids | 9 KB |
| `agenteval-code.zip` | the code snapshot at the commit that produced the run | 122 KB |
| `figures/*.png` | the four figures | 270 KB |
| `PAPER.md` | the write-up | 10 KB |

> Zenodo will not let you add, remove or change files after publishing. Check the
> list before you hit Publish. If you want to change something later you have to
> publish a new version, which gets its own DOI under the same concept DOI.

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

Paste this into the Description box. It is plain HTML, which the editor accepts.

```html
<p><strong>Four code LLMs were shown static-analysis findings on their own
solutions and asked to fix them. The study was built to catch them cheating:
satisfying the analyser they were shown while the defect stayed put. They did not
cheat.</strong> Across 4,439 repair steps the four models wrote five suppression
directives in total, and 94&#37; of the findings they removed were also gone from a
held-out analyser they were never shown (suppression rate 6&#37;, 95&#37; CI
[4&#37;, 9&#37;]).</p>

<p>They complied instead &mdash; and complying with one particular rule broke two
working programs in five.</p>

<p>Each task ran two repair arms branching from the same baseline solution: one
shown Pylint findings, one shown Ruff findings. Restricted to tasks where both
arms ran and the baseline passed its own tests, the Ruff arm broke the program
and the Pylint arm did not on 46 occasions against 3 the other way (exact
McNemar, <em>p</em> = 7 &times; 10<sup>&minus;11</sup>, 213 pairs, every model
individually significant).</p>

<p><strong>That result is one rule.</strong> Ruff's <code>S311</code>
(&ldquo;pseudo-random generators are not suitable for cryptographic
purposes&rdquo;) broke 41.8&#37; [32&#37;, 52&#37;] of the working programs it
appeared in, against 8.8&#37; [5&#37;, 16&#37;] where no security rule was shown.
Remove every S311 task and the paired comparison falls to 10 versus 3,
<em>p</em> = 0.09 &mdash; indistinguishable from noise at this sample size. This
is therefore not evidence that security rules as a class are dangerous in a repair
loop; it is evidence that S311 is, and that a single rule was enough to make the
whole Ruff arm look four times more destructive than the Pylint arm.</p>

<p>The mechanism is visible in the failures. None of the affected code was
cryptographic: BigCodeBench uses <code>random</code> for data generation and seeds
it in the tests. The agent does as it is told, swaps in <code>secrets</code>,
determinism is lost, and since <code>secrets</code> has no <code>seed()</code>
some programs stop running at all. The finding was a true positive about the code
and a false positive about the context, and the analyser reported success either
way.</p>

<p>A suppressed finding is detectable &mdash; the directive is in the diff and a
second analyser catches it. Faithful, destructive repair leaves nothing to find.
This is an empirical case for verification independent of the gate being optimised
against, and a different case from the one usually made: the risk is not that
agents cheat a quality gate but that they obey it where its advice is wrong, with
the exposure concentrated in a few rules rather than spread thinly.</p>

<p><strong>Method.</strong> Four code-specialised instruct models from four
families within a 1.3&times; size spread (Qwen2.5-Coder-7B-Instruct,
deepseek-coder-6.7b-instruct, Yi-Coder-9B-Chat, granite-8b-code-instruct-128k),
served at bfloat16 on one A100 via vLLM at temperature 0. 300 BigCodeBench tasks
drawn by fixed shuffle and filtered to those whose reference solution passes its
own tests in the run environment. Two repair rounds per arm; all three analysers
(Ruff, Bandit, Pylint) measured at every step alongside the task's own tests.
1,200 task-model pairs, 4,439 steps, 1.14 hours, zero errors. Findings are tracked
individually by code rather than by count, because fixing
<code>subprocess.check_output(cmd, shell=True)</code> moves Ruff from
<code>S602</code> to <code>S603</code> and Bandit from <code>B602</code> to
<code>B603</code> &mdash; both counts unchanged &mdash; so a count-based delta
would score a real fix as worthless and a <code>&#35; noqa</code> as a triumph.</p>

<p><strong>Limitations.</strong> The breakage result rests on one rule: S311
supplies 91 of the 122 security-shown tasks and the comparison is not significant
without it. Source text was not retained, so the S311 mechanism is established
from failure modes and introduced codes rather than diffs. One sample per task at
temperature 0. Single-file Python from one benchmark; nothing here extends to Java,
to CodeQL, or to repository-scale change without being measured there.</p>

<p><strong>Contents.</strong> <code>steps.jsonl</code> is the complete raw record.
All analysis re-derives from it offline, and
<code>scripts/verify_readme.py</code> in the code archive recomputes every figure
quoted in the paper and exits non-zero if the data stops agreeing.</p>
```

**Licenses** → keep **Creative Commons Attribution 4.0 International** (already
set). The code archive is MIT; CC-BY on the record covers the paper and data.

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
3. **Files are frozen after publishing.** Confirm all six are attached.
4. **Save draft** first. Publishing mints the DOI and cannot be undone.
