# The run

`steps.jsonl` is the complete raw record of the study: one JSON object per step,
where a step is the state of one solution at one point in the loop.

| field | meaning |
|---|---|
| `task_id`, `model` | which BigCodeBench task, which model |
| `arm` | `baseline`, `shown_pylint`, or `shown_ruff` |
| `round` | 0 for the baseline, then 1..2 |
| `shown_tool` | the analyser whose findings the agent was given |
| `findings` | every analyser's findings as `[code, line]`, including the ones the agent never saw |
| `tests_passed`, `test_detail` | the task's own tests against this revision |
| `suppressions_added` | net new `# noqa` / `# nosec` / `# pylint: disable` directives |
| `completion_tokens`, `source_chars` | size of the reply and the resulting file |

`run_manifest.json` records the models, seed, budgets, analyser and vLLM
versions, the git commit that produced the run, and the 300 task ids.

Every table and figure in the paper re-derives from `steps.jsonl` offline:

    python scripts/verify_readme.py data/steps.jsonl
    python scripts/make_figures.py data/steps.jsonl figures/

The first recomputes all 23 figures quoted in the write-up and exits non-zero if
the data stops agreeing with them.

Source text of each revision was **not** retained, which is the study's main
reproducibility limitation and is stated as such in the paper.
