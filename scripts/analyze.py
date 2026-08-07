"""Cross-model ablation analysis.

Thin wrapper over `agenteval report`. This script used to carry its own copy of the
comparison logic, which drifted into printing bare solve-rate deltas with no interval
and no significance test — the presentation that produced the original overclaimed
headline. Rather than maintain two analysis paths that can disagree, it now delegates
to the one that reports uncertainty.

Run: python scripts/analyze.py [--suite core]
"""

from __future__ import annotations

import argparse

from agenteval.ablation import report


def main() -> None:
    p = argparse.ArgumentParser(description="print the pooled ablation comparison")
    p.add_argument("--suite", default=None, help="limit to one suite (default: all runs)")
    p.add_argument("--output-dir", default="results")
    args = p.parse_args()
    report(args.suite, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
