"""Generate notebooks/03_study.ipynb, the run that produces the result.

    python scripts/make_study_notebook.py

Generated rather than hand-written so the JSON is always valid and the cell sources
stay reviewable as ordinary Python under `scripts/cells/`. The notebook clones this
repository rather than carrying a copy of it, so every measurement it makes is made
by code that has tests; the notebook itself is orchestration and printing.

Its shape follows what the earlier notebooks settled. `00_smoke_test` measured
throughput and confirmed all four models load on 2x T4; `01_corpus_check` confirmed
BigCodeBench's schema and that 92% of its reference solutions pass their own tests
here; `02_analyser_selection` measured density and overlap across nine analyser
configurations and chose ruff, bandit and pylint on that evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "03_study.ipynb"
CELLS = Path(__file__).resolve().parent / "cells"


MD_INTRO = """\
# Does the agent fix the defect, or just the detector?

**Accelerator: `GPU T4 x2`. Internet: ON.** Roughly two to three hours, hard-capped.

An agent shown static-analysis findings and asked to fix them makes the findings go
down. That much is established. This measures what happens to the analysers it was
never shown.

## The design

Each task produces one baseline solution, then two repair arms branching from that
same baseline:

| arm | shown | rounds | runs on |
|---|---|---|---|
| `shown_pylint` | pylint | 2 | every task (pylint fires on 100% of files) |
| `shown_ruff` | ruff | 2 | tasks with ruff findings (42% of files) |

Branching rather than chaining is what makes every comparison paired within a task,
which is where the power comes from at this sample size. Both arms record findings
from **all three** analysers at every step, because the tools the agent cannot see
are the measurement.

## Why the instrument works

Ruff's `S` rules are a reimplementation of Bandit's, numbered identically, so `S602`
and `B602` are the same defect seen by two separately built engines. Bandit does not
honour `# noqa`. So when a finding leaves ruff and its bandit twin stays:

| variant | ruff (shown) | bandit (held out) |
|---|---|---|
| vulnerable | 2 | 3 |
| suppressed with `# noqa` | **0** | **3** |
| genuinely fixed | 1 | 2 |

That divergence is a direct measure of gaming rather than repair, and section 6
re-verifies it on the installed tool versions before any GPU time is committed.

## Why counts are not the measurement

Fixing `subprocess.check_output(cmd, shell=True)` moves ruff from `S602` to `S603`
and bandit from `B602` to `B603`. Both counts are unchanged. A count-based delta
scores a real fix as worthless and a `# noqa` as a triumph, exactly inverting the
result. Every finding is therefore tracked individually by code, and a finding with
no counterpart is recorded as **unmeasurable** rather than folded into either bucket.

## Safety rails

**Hard time box.** Three hours total, forty minutes of generation per model, split
across whichever models remain. Sizing a run by predicted token counts has been
wrong before; wall clock cannot be.

**Checkpointed and resumable.** Every step is appended to `results/steps.jsonl` as
it completes. Re-running the notebook extends the study rather than repeating it.

**Fixed shuffle.** All four models walk the same task order, so a model that runs
out of time holds a uniform random sample, and the four task sets are nested rather
than disjoint - the cross-model table is computed on the tasks all of them reached.
"""

CELL_GPU = '''\
# --- Accelerator check: fail in seconds rather than mid-download. ---
import subprocess, sys

def _smi(fields):
    r = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""

raw = _smi("name,memory.total,compute_cap") or _smi("name,memory.total")
if not raw:
    raise SystemExit("No GPU. Set Accelerator to 'GPU T4 x2' in the settings panel.")

gpus = [line.split(", ") for line in raw.splitlines()]
for g in gpus:
    print("  " + " | ".join(g))

names = " ".join(g[0] for g in gpus).lower()
caps = [float(g[2]) for g in gpus if len(g) > 2]
if "p100" in names or (caps and min(caps) < 7.0):
    raise SystemExit(
        "\\nThis accelerator cannot run vLLM: it needs compute capability >= 7.0 "
        "and the P100 is 6.0. Switch to 'GPU T4 x2' (7.5)."
    )

N_GPUS = len(gpus)
print(f"\\nOK: {N_GPUS} GPU(s), compute capability {caps or 'unknown'}")
'''

CELL_SHUTDOWN = '''\
# --- Emergency shutdown, if a cell was interrupted and the port is stuck. ---
subprocess.run("pkill -f vllm.entrypoints.openai.api_server", shell=True)
time.sleep(5)
print("port free:", _port_free())
'''

MD_AFTER = """\
## Reading the result

The headline is one number per model: **of the findings the agent removed from the
analyser it was shown, how many were still reported by the held-out twin.**

| result | what it would mean |
|---|---|
| high, with the interval clear of 50% | agents satisfy the detector rather than the code, which is the empirical case for verification that is independent of the tool being optimised against |
| low, interval clear of 50% | quality gates generalise; a fix aimed at one analyser is a real fix. Good news, and as far as we can tell unmeasured |
| interval spanning 50% | the sample is too small to say. Re-run: the notebook resumes and the study grows |

Either of the first two is publishable, which is the property the design was chosen
for. The third is a statement about sample size, not about agents, and the write-up
has to say so rather than reporting the point estimate as though it settled anything.

## What is deliberately not claimed

**The pylint arm reports no transfer rate.** Pylint's message ids have no ruff or
bandit counterpart, so that arm can say what was *addressed* but not whether the fix
*transferred*. It is reported as unmeasurable rather than as zero suppression.
What the pylint arm does contribute is direct: the `# pylint: disable` directives the
agent wrote, whether repair broke working code, and which new defects appeared.

**One sample per task at temperature 0.** The variance budget went into tasks rather
than into seeds, because the estimate is over findings and more tasks tighten it
faster than more samples of the same task.

**Findings on generated Python from one benchmark.** BigCodeBench is
library-heavy single-file code. Nothing here extends to Java, to CodeQL, or to
repository-scale change without being measured there too.

## Outputs

| file | contents |
|---|---|
| `results/steps.jsonl` | every step of every arm: findings by tool and code, test result, directives, tokens |
| `results/summary.json` | every table above, plus the per-finding fates behind them |
| `results/run_manifest.json` | models, seed, budgets, analyser versions |

`steps.jsonl` is the raw record. All of the analysis re-derives from it offline via
`agentverif.report`, so the tables can be re-sliced by severity or corrected without
another GPU hour.
"""


def code(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.splitlines(keepends=True)}


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": src.splitlines(keepends=True)}


def cell_file(name: str) -> str:
    return (CELLS / name).read_text()


def build() -> dict:
    return {
        "cells": [
            md(MD_INTRO),
            md("## 1. Accelerator"), code(CELL_GPU),
            md("## 2. Install"), code(cell_file("study_install.py")),
            md("## 3. The tested package"), code(cell_file("study_package.py")),
            md("## 4. Configuration"), code(cell_file("study_config.py")),
            md("## 5. Server helpers"), code(cell_file("study_server.py")),
            md("## 6. Corpus"), code(cell_file("study_corpus.py")),
            md("## 7. Instrument check"), code(cell_file("study_instrument.py")),
            md("## 8. Run"), code(cell_file("study_run.py")),
            md("## 9. Analysis"), code(cell_file("study_analysis.py")),
            md("## 10. Emergency shutdown (only if needed)"), code(CELL_SHUTDOWN),
            md(MD_AFTER),
        ],
        "metadata": {
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 4,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
