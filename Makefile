.PHONY: install benchmark validate power baseline ablate ablate-fast analyze report dashboard swebench test clean reproduce

# Three small tiers by default. A capability *curve* needs three points, and the
# tiers must have headroom: a model that already solves ~everything cannot show an
# ablation's effect (the 7B sat at 92% in v1, where four of five levers read +0).
# Override for a bigger tier: make ablate MODEL_TIERS="qwen2.5-coder:7b"
MODEL_TIERS ?= qwen2.5-coder:0.5b qwen2.5-coder:1.5b qwen2.5-coder:3b
MODEL_MAIN  ?= qwen2.5-coder:1.5b
SEEDS       ?= 3
SUBSET      ?= smoke

install:            ## install the package (local deps only)
	uv venv
	uv pip install -e ".[dev]"

benchmark:          ## (re)generate the synthetic local benchmark
	.venv/bin/python scripts/build_local_benchmark.py

validate:           ## every task must be genuinely broken AND provably solvable
	.venv/bin/python scripts/validate_benchmark.py

power:              ## how many tasks are needed to detect an effect of a given size
	.venv/bin/agenteval power --effect 0.2

models:             ## pull every model tier the default sweep uses
	for m in $(MODEL_TIERS); do ollama pull $$m; done

baseline:           ## run one baseline condition on the local benchmark
	.venv/bin/agenteval run --name baseline --provider local --subset $(SUBSET) --model $(MODEL_MAIN)

ablate:             ## full sweep: every condition x $(SEEDS) seeds x every model tier
	for m in $(MODEL_TIERS); do \
		.venv/bin/agenteval ablate --suite core --model $$m --subset $(SUBSET) --seeds $(SEEDS); \
	done

ablate-one:         ## full sweep on a single tier — start here to sanity-check the pipeline
	.venv/bin/agenteval ablate --suite core --model $(MODEL_MAIN) --subset $(SUBSET) --seeds $(SEEDS)

ablate-fast:        ## single-seed sweep on one tier — a smoke test, not evidence
	.venv/bin/agenteval ablate --suite core --model $(MODEL_MAIN) --subset $(SUBSET) --seeds 1

analyze: report     ## alias kept for muscle memory

report:             ## re-print the pooled comparison table from existing runs
	.venv/bin/agenteval report --suite core

dashboard:          ## render the HTML report + refresh README results
	.venv/bin/agenteval dashboard

swebench:           ## run the same agent against the SWE-bench Verified smoke subset
	.venv/bin/agenteval ablate --suite core --provider swebench --subset verified_smoke \
		--model $(MODEL_MAIN) --seeds 1

test:               ## fast unit tests (no model calls)
	.venv/bin/python -m pytest tests/ -q

clean:
	rm -rf results/core__* results/dashboard.html results/*.log

reproduce: install benchmark validate ablate report dashboard  ## full pipeline
