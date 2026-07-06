# Running against SWE-bench Verified

The `swebench` provider runs the **same agent loop** used on the local benchmark against
real GitHub-issue tasks, and scores patches with the **official** SWE-bench evaluation
harness — so the solve rate is directly comparable to the public leaderboard.

## Install

```bash
uv pip install -e ".[swebench]"   # pulls datasets + swebench
```

Docker must be running. The harness starts one container per instance (repo checked out at
the base commit at `/testbed`), the agent acts via `docker exec`, and evaluation is done by
`swebench.harness.run_evaluation`.

## Apple Silicon note

SWE-bench's prebuilt evaluation images are `x86_64`. On an M-series Mac they run under
emulation (correct, but slower), or you can build `arm64` images locally. Two options:

1. **Emulation (simplest):** enable Rosetta for Docker (Docker Desktop → Settings →
   General → *Use Rosetta for x86/amd64 emulation*). Works out of the box, ~2–4× slower.
2. **Native arm64:** let the `swebench` harness build images for your subset the first time
   you evaluate (`--cache_level instance`). Slower first run, fast thereafter.

Start with a **small subset** to keep image build/pull time bounded.

## Run a smoke subset

```bash
# 1. curate / edit the instance list
cat subsets/verified_smoke.txt

# 2. run the agent on it (local model = free)
agenteval run --name swe_baseline --provider swebench --subset verified_smoke \
  --model qwen2.5-coder:7b --max-steps 30

# 3. compare conditions and render the report
agenteval run --name swe_no_test --provider swebench --subset verified_smoke \
  --model qwen2.5-coder:7b --max-steps 30 --no-repo-map
agenteval dashboard swe_baseline swe_no_test
```

## Scaling up

- Swap in a stronger local model for the headline number: `ollama pull qwen2.5-coder:32b`
  (≈18 GB at 4-bit, fits in 36 GB unified memory), then `--model qwen2.5-coder:32b`.
- Grow `subsets/verified_smoke.txt` toward the full 500-instance Verified split as your
  Docker image cache and patience allow.
- Every run persists trajectories + metrics under `results/<name>/`, so partial runs
  accumulate and the failure taxonomy sharpens as coverage grows.

## What to report

Report the **failure-mode distribution** alongside the solve rate. On SWE-bench the taxonomy
typically shifts toward `no_edit` (localization is the dominant bottleneck on large repos)
and `patch_apply_failed` (edit formatting on real diffs) — which is exactly the signal that
tells you *where* to invest.
