# Findings

Local benchmark: 12 single-file Python bug-fix tasks, hidden pytest oracle. Two base models
(Qwen2.5-Coder 1.5B and 7B via Ollama, temperature 0). Each ablation flips one `AgentConfig`
field vs. the baseline. All numbers are `results/core__*/metrics.json`.

## Solve rate by condition × model

| condition | 1.5B | 7B |
|---|---|---|
| baseline | 42% (5/12) | 92% (11/12) |
| − run_tests tool | **8% (−33)** | 92% (+0) |
| − repo map | 58% (+17) | 92% (+0) |
| windowed history | 42% (+0) | 92% (+0) |
| best-of-3 | 42% (+0) | 92% (+0) |

## 1. Scaffolding value is inversely proportional to base-model capability

The single biggest lever — the `run_tests` tool — is worth **+33 points for the 1.5B model
and 0 for the 7B**. The 7B model solves these tasks from the problem statement alone, so no
amount of tool/context scaffolding moves it. The 1.5B model depends on the feedback loop.

**Implication:** scaffolding ROI must be measured *per model tier*. A tool that looks
worthless on your strongest model may be load-bearing on a smaller/cheaper one — relevant when
choosing what to ship on a latency- or cost-constrained deployment.

## 2. The failure taxonomy explains *why* the tool matters

Removing `run_tests` doesn't just lower the score — it changes the *shape* of failure:

| failure mode | 1.5B baseline | 1.5B − run_tests |
|---|---|---|
| solved | 5 | 1 |
| max_steps | 4 | **9** |
| no_edit | 2 | 2 |
| wrong_fix | 1 | 0 |

Without a way to check its work, the agent can't tell whether it's done, so it spins until the
step budget runs out: `max_steps` failures more than double (4 → 9). The verification loop
isn't just improving fixes — it's letting the agent *terminate confidently*. This is the kind
of mechanistic read a raw solve rate can't give you.

## 3. More context is not always better

Removing the repo-file map *improved* the 1.5B model by **+17 points** (42% → 58%). For these
small single-file tasks the file listing is low-signal, and it appears to distract a
capacity-limited model more than it helps. Context construction is a tuning problem, not a
"more is better" one — worth an A/B rather than an assumption.

_(N = 12, so treat this as directional; the effect is large enough and the mechanism plausible
enough to warrant a bigger run, not to bank on the exact magnitude.)_

## 4. Best-of-N needs sampling diversity

Best-of-3 gave **+0** for both models — because at temperature 0 the three independent rollouts
are identical, so there is nothing to select over. The harness dutifully ran 3× the tokens for
no gain. Correct next step: raise temperature (or vary the prompt) for multi-sample conditions.
A good example of an ablation surfacing a config bug rather than a capability limit.

---

## Resume bullets (pick 1–2)

- Built a benchmark-agnostic evaluation harness for LLM coding agents (Python, ReAct loop,
  OpenAI-compatible model access, Docker-based SWE-bench provider) that measures solve rate,
  logs full trajectories, and classifies failures into a 7-mode taxonomy.
- Ran controlled ablations across two model tiers and showed the `run_tests` verification tool
  is worth **+33 pts solve rate for a 1.5B model but 0 for a 7B** — quantifying that scaffolding
  ROI is inversely proportional to base-model capability.
- Used the failure taxonomy to explain the mechanism (removing verification doubled
  `max_steps` non-termination, 4→9), and caught a multi-sampling bug where temperature-0
  best-of-N wasted 3× tokens for no gain.
