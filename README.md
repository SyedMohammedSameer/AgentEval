# agenteval — an evaluation harness for LLM coding agents

A benchmark-agnostic harness that runs an LLM coding agent against software-engineering
tasks, measures **solve rate**, records full **trajectories**, classifies **failure modes**,
and runs controlled **ablations** to attribute solve-rate changes to specific agent design
choices (context construction, tool availability, retry strategy).

Everything runs locally against an open-weights model (Qwen2.5-Coder via Ollama) — **no API
or GPU spend**. The same code targets any OpenAI-compatible endpoint by changing one config
object, and a SWE-bench provider plugs into the identical agent loop.

## Why this exists

Raw pass/fail hides *why* an agent fails. This harness separates:

| Failure mode | What it means | The fix it points to |
|---|---|---|
| `no_edit` | agent never edited a file | localization / confidence |
| `patch_apply_failed` | diff was malformed | edit formatting |
| `wrong_fix` | patch applied, tests still fail | reasoning / correctness |
| `max_steps` | ran out of budget mid-solve | efficiency / planning |
| `protocol_violation` | couldn't emit a valid action | instruction following |
| `eval_timeout` | patch hung the test suite | introduced regression |

Turning a solve-rate number into a *failure distribution* is what makes the results
actionable — and is the daily work of an applied-agent team.

## Architecture

```
provider (local | swebench)      # loads tasks, builds sandboxes, scores patches
        │
        ▼
   Environment  ◄──────  Agent (ReAct loop)  ◄──────  LLMClient (OpenAI-compatible)
   exec / diff            think → act → observe        local Ollama or any API
        │
        ▼
   Trajectory  ──►  failure_taxonomy  ──►  metrics  ──►  HTML dashboard
```

- **Benchmark-agnostic:** the agent only sees `exec` + patch operations, so the local
  synthetic benchmark and SWE-bench share one agent implementation.
- **Ablation-ready:** every behavioral knob lives on `AgentConfig`; an experiment is a
  single field flip.
- **Reproducible:** each run persists its config, per-task trajectories, and metrics.

## Quickstart

```bash
# 1. install (dev deps only — no Docker/SWE-bench needed)
uv venv && uv pip install -e .

# 2. get a local model
ollama pull qwen2.5-coder:7b

# 3. build the local benchmark and run a baseline
python scripts/build_local_benchmark.py
agenteval run --name baseline --provider local --subset smoke

# 4. run an ablation and render the report
agenteval ablate --suite core
agenteval dashboard
open results/dashboard.html
```

## Results

<!-- RESULTS:START -->

**Finding — scaffolding value is inversely proportional to base-model capability.** Removing the `run_tests` tool: `qwen2.5-coder:1.5b` 42%→8% (-33 pts); `qwen2.5-coder:7b` 92%→92% (+0 pts). Cells show solve rate and Δ vs the same model's baseline (12 tasks each). _best-of-3 shows +0 because temperature=0 makes the rollouts identical — the fix is to raise temperature for multi-sampling._

| condition | `qwen2.5-coder:1.5b` | `qwen2.5-coder:7b` |
|---|---|---|
| baseline | **42%** | **92%** |
| − run_tests tool | 8% (-33) | 92% (+0) |
| − repo map (context) | 58% (+17) | 92% (+0) |
| windowed history | 42% (+0) | 92% (+0) |
| best-of-3 (retry) | 42% (+0) | 92% (+0) |

<!-- RESULTS:END -->

Full write-up with the failure-mode mechanism in [docs/findings.md](docs/findings.md);
interactive report at `results/dashboard.html` (`make dashboard`).

## The local benchmark

Twelve self-contained Python bug-fix tasks (`benchmarks/local/`), each with a genuine bug, a
*visible* basic test the agent can run, and a *hidden* oracle used only for scoring — mirroring
"you have some tests, CI has more." Authored by `scripts/build_local_benchmark.py` and checked
by `scripts/validate_benchmark.py` (every buggy workspace must fail its own oracle).

## SWE-bench

`--provider swebench` runs the same agent against SWE-bench Verified using the official
Docker-based evaluation. See [docs/swebench.md](docs/swebench.md) for the Apple-Silicon setup
and curated arm64 smoke subset.

## License

MIT
