.PHONY: install benchmark validate baseline ablate analyze dashboard test clean

install:            ## install the package (local deps only)
	uv venv
	uv pip install -e ".[dev]"

benchmark:          ## (re)generate the synthetic local benchmark
	.venv/bin/python scripts/build_local_benchmark.py

validate:           ## check every task's buggy code fails its oracle
	.venv/bin/python scripts/validate_benchmark.py

baseline:           ## run one baseline condition on the local benchmark
	.venv/bin/agenteval run --name baseline --provider local --subset smoke

ablate:             ## run the core ablation suite across two model sizes
	.venv/bin/agenteval ablate --suite core --model qwen2.5-coder:7b   --subset smoke
	.venv/bin/agenteval ablate --suite core --model qwen2.5-coder:1.5b --subset smoke

analyze:            ## print the cross-model scaffolding-value table
	.venv/bin/python scripts/analyze.py

dashboard:          ## render the HTML report + refresh README results
	.venv/bin/agenteval dashboard

test:               ## fast unit tests (no model calls)
	.venv/bin/python -m pytest tests/ -q

clean:
	rm -rf results/core__* results/dashboard.html results/*.log

reproduce: install benchmark validate ablate analyze dashboard  ## full pipeline
