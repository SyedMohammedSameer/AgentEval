"""Generate notebooks/01_corpus_check.ipynb.

CPU-only. Costs no GPU quota. Answers, before any generation is run:

  1. Does the corpus load, and what is its actual schema?
  2. Do its reference solutions pass their own tests on Kaggle's image?
  3. What share of tasks carry a static-analysis finding at all?
  4. Given 2 and 3, how long does the real study take?

Question 3 is the one that sets the budget: the study can only measure whether a
fix transfers on code that had something to fix.

    python scripts/make_corpus_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "01_corpus_check.ipynb"
CELLS = Path(__file__).resolve().parent / "cells"


MD_INTRO = """\
# Corpus check: can BigCodeBench carry this study?

**CPU only. Set Accelerator to `None`** so this costs nothing from your GPU quota.
**Internet ON** for the dataset and the analysers. Runs in roughly 20-30 minutes.

## Why this exists

Correctness measurement is not optional. Without it, an agent that "fixes" a
finding by deleting the function looks like a success. So the corpus is only
usable if its own reference solutions pass their own tests on this machine, and
BigCodeBench reaches into a long tail of third-party libraries that Kaggle's image
may not carry.

The second thing it settles is the number that actually sets the budget: **what
share of tasks carry a static-analysis finding at all.** Transfer can only be
measured on code that had something to fix, so that share decides how many tasks
must be generated to reach the 150 analysable ones the power calculation asks for.

## What it decides

| measurement | what it changes |
|---|---|
| reference solutions that run | whether correctness is measurable, and the real corpus size |
| finding hit rate per rule set | which rules the agent is shown, and the screening cost |
| semgrep availability | whether the cross-engine held-out arm survives |
| seconds per task | whether CPU-side test execution can overlap generation |

It produces no research result. It converts four assumptions into four numbers.
"""

MD_INSTALL = "## 1. Install"
CELL_INSTALL = '''\
# CPU-only: no vLLM, no torch, no GPU.
import subprocess
for pkg in ("datasets", "ruff", "bandit", "semgrep", "radon"):
    r = subprocess.run(f"pip install -q {pkg}", shell=True, text=True)
    print(f"{pkg:10s} {'ok' if r.returncode == 0 else 'FAILED'}")
'''

MD_AFTER = """\
## Reading the verdict

**Both rates healthy** -> the corpus is confirmed and the printed GPU estimate is
built from your own measured throughput rather than from an assumption.

**Runnable share below 50%** -> correctness cannot be measured for most of the
corpus. Run the fallback cell.

**Hit rate below 15% everywhere** -> the problem is usually the rule selection
rather than the dataset. Widening the rules is the first thing to try; changing
corpus is the second.

**Semgrep unavailable** -> the study still works on the Ruff/Bandit pair, which is
the sharper of the two comparisons anyway, but it loses the cross-engine arm and
the write-up has to say so.

## A caveat worth carrying into the paper

The hit rates here are measured on curated reference solutions. Model-generated
code is generally messier, so the real screening hit rate should be at least this
high. Every estimate downstream treats these as lower bounds.
"""


def code(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.splitlines(keepends=True)}


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": src.splitlines(keepends=True)}


def cell_file(name: str) -> dict:
    return code((CELLS / name).read_text())


def build() -> dict:
    return {
        "cells": [
            md(MD_INTRO),
            md(MD_INSTALL), code(CELL_INSTALL),
            md("## 2. Load the corpus and learn its schema"), cell_file("corpus_load.py"),
            md("## 3. Do the reference solutions run?"), cell_file("corpus_exec.py"),
            md("## 4. How many tasks have anything to fix?"), cell_file("corpus_analyse.py"),
            md("## 5. Verdict and cost"), cell_file("corpus_verdict.py"),
            md("## 6. Fallback (run only if the verdict said STOP)"),
            cell_file("corpus_fallback.py"),
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
