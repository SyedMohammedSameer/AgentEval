"""Generate notebooks/02_analyser_selection.ipynb.

CPU-only, roughly 10-15 minutes, no GPU quota.

The corpus check settled that BigCodeBench works: 92% of its reference solutions
pass their own tests here, and the schema and assembly are known. It also turned
up two problems that this notebook resolves with measurement rather than guesswork.

Semgrep's p/python pack reported nothing across 25 solutions, which would leave
Bandit as the only held-out analyser, and Bandit is a Ruff reimplementation.
Without a second, independently built tool the study can show that agents suppress
findings but not that a fix fails to generalise across engines.

Findings are also sparse, around 1.5 per task among tasks that have any, so the
analysis has to work per finding rather than per task, and the shown analyser
needs enough density to give the agent something to work on.

    python scripts/make_analyser_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "02_analyser_selection.ipynb"
CELLS = Path(__file__).resolve().parent / "cells"


MD_INTRO = """\
# Analyser selection

**CPU only, Accelerator `None`. Internet ON.** 10-15 minutes.

The corpus is settled: BigCodeBench loads, 92% of its reference solutions pass
their own tests here, and assembly is `complete_prompt + canonical_solution`.

Two things it left open, both of which decide the study's design:

**Semgrep found nothing.** Its `p/python` pack fired on zero of 25 solutions. If no
independently built analyser sees these files, the only held-out tool is Bandit,
and Bandit is a reimplementation of Ruff's `S` rules. That pairing still detects
suppression, which is the sharpest single test, but it cannot show that a fix fails
to generalise across engines.

**Findings are sparse.** Roughly 1.5 per task among tasks that have any. The study
therefore reasons per finding rather than per task, and the shown analyser needs
enough density to give the agent real work.

This notebook measures nine candidate analyser configurations on the same corpus
and reports, for each: how many files it fires on, how dense it is, and how much it
overlaps line-for-line with every other candidate.

## What the design needs from a pair

| property | why |
|---|---|
| density | the agent needs findings to fix |
| overlap | a genuine fix must be visible to the held-out tool, or the comparison measures two different questions |
| independence | satisfying one tool must not trivially satisfy the other |

Bandit against `ruff[S]` already gives the suppression test. What this looks for is
a second pairing with real overlap and a genuinely different engine.
"""

CELL_INSTALL = '''\
# CPU only.
import subprocess
for pkg in ("datasets", "ruff", "bandit", "semgrep", "pylint", "mypy"):
    r = subprocess.run(f"pip install -q {pkg}", shell=True, text=True)
    print(f"{pkg:10s} {'ok' if r.returncode == 0 else 'FAILED'}")
'''

CELL_LOAD = '''\
# Same corpus, same shuffle, so this analyses the same tasks the study will use.
import random
from datasets import load_dataset

ds = load_dataset("bigcode/bigcodebench", "default")
records = ds[list(ds.keys())[0]]
order = list(range(len(records)))
random.Random(0).shuffle(order)
print(f"{len(records)} tasks; first ids "
      f"{[records[i]['task_id'] for i in order[:5]]}")
'''

MD_AFTER = """\
## Choosing from the output

**A dense shown analyser.** Something firing on well over half the files, so
screening does not dominate the budget. `ruff[S,B,SIM,RET,ARG,PERF,C90]` is the
broad candidate; the risk is that it drifts into style noise that says nothing
about defects.

**Bandit stays as the suppression detector.** It reimplements Ruff's `S` rules and
ignores Ruff's `# noqa`, which is what makes divergence between them unambiguous
evidence of gaming rather than fixing.

**A cross-engine partner with real overlap.** Whichever of the semgrep configs,
pylint, or mypy shows meaningful line overlap with the shown analyser. Pylint is
the most likely: a genuinely separate implementation with overlapping concerns
around unused names, broad excepts, and dead code.

**If nothing has overlap**, the study narrows honestly to the suppression question
alone: *do agents suppress findings rather than fix them?* That is still novel,
still Sonar-shaped, and still worth publishing. It just cannot also claim anything
about generalisation across engines, and the write-up has to say so plainly rather
than quietly reporting one comparison as though it were two.
"""


def code(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.splitlines(keepends=True)}


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": src.splitlines(keepends=True)}


def build() -> dict:
    return {
        "cells": [
            md(MD_INTRO),
            md("## 1. Install"), code(CELL_INSTALL),
            md("## 2. Load the corpus"), code(CELL_LOAD),
            md("## 3. Measure every candidate"),
            code((CELLS / "analyser_select.py").read_text()),
            md(MD_AFTER),
        ],
        "metadata": {
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
