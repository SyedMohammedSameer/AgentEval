.PHONY: install benchmark validate power baseline ablate ablate-fast analyze report dashboard swebench test clean reproduce

MODEL_SMALL ?= qwen2.5-coder:1.5b
MODEL_LARGE ?= qwen2.5-coder:7b
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

baseline:           ## run one baseline condition on the local benchmark
	.venv/bin/agenteval run --name baseline --provider local --subset $(SUBSET) --model $(MODEL_LARGE)

ablate:             ## full sweep: every condition x $(SEEDS) seeds x two model sizes
	.venv/bin/agenteval ablate --suite core --model $(MODEL_LARGE) --subset $(SUBSET) --seeds $(SEEDS)
	.venv/bin/agenteval ablate --suite core --model $(MODEL_SMALL) --subset $(SUBSET) --seeds $(SEEDS)

ablate-fast:        ## single-seed sweep on the small model — a smoke test, not evidence
	.venv/bin/agenteval ablate --suite core --model $(MODEL_SMALL) --subset $(SUBSET) --seeds 1

analyze: report     ## alias kept for muscle memory

report:             ## re-print the pooled comparison table from existing runs
	.venv/bin/agenteval report --suite core

dashboard:          ## render the HTML report + refresh README results
	.venv/bin/agenteval dashboard

swebench:           ## run the same agent against the SWE-bench Verified smoke subset
	.venv/bin/agenteval ablate --suite core --provider swebench --subset verified_smoke \
		--model $(MODEL_LARGE) --seeds 1

test:               ## fast unit tests (no model calls)
	.venv/bin/python -m pytest tests/ -q

clean:
	rm -rf results/core__* results/dashboard.html results/*.log

reproduce: install benchmark validate ablate report dashboard  ## full pipeline
