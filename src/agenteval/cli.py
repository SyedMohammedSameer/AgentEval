"""Command-line interface: `agenteval run|ablate|dashboard`."""

from __future__ import annotations

import argparse

from .config import AgentConfig, ModelConfig, RunConfig


def _run_cfg_from_args(a) -> RunConfig:
    return RunConfig(
        name=a.name,
        provider=a.provider,
        subset=a.subset,
        model=ModelConfig(model=a.model, temperature=a.temperature),
        agent=AgentConfig(
            max_steps=a.max_steps,
            use_test_tool=not a.no_test_tool,
            include_repo_map=not a.no_repo_map,
            history_strategy=a.history,
            self_check=not a.no_self_check,
            attempts=a.attempts,
        ),
        output_dir=a.output_dir,
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="agenteval", description="LLM coding-agent eval harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one experimental condition")
    r.add_argument("--name", default="baseline")
    r.add_argument("--provider", default="local", choices=["local", "swebench"])
    r.add_argument("--subset", default="smoke")
    r.add_argument("--model", default="qwen2.5-coder:7b")
    r.add_argument("--temperature", type=float, default=0.0)
    r.add_argument("--max-steps", type=int, default=20)
    r.add_argument("--attempts", type=int, default=1)
    r.add_argument("--history", default="full", choices=["full", "windowed"])
    r.add_argument("--no-test-tool", action="store_true", help="ablation: remove run_tests tool")
    r.add_argument("--no-repo-map", action="store_true", help="ablation: remove repo file map from context")
    r.add_argument("--no-self-check", action="store_true", help="ablation: disable self-verification")
    r.add_argument("--output-dir", default="results")

    d = sub.add_parser("dashboard", help="render an HTML report over one or more runs")
    d.add_argument("runs", nargs="*", help="run names under results/ (default: all)")
    d.add_argument("--output-dir", default="results")
    d.add_argument("--out", default="results/dashboard.html")

    a = sub.add_parser("ablate", help="run a predefined ablation sweep")
    a.add_argument("--suite", default="core", help="ablation suite name (see scripts/ablation.py)")
    a.add_argument("--model", default="qwen2.5-coder:7b")
    a.add_argument("--subset", default="smoke")
    a.add_argument("--provider", default="local")

    args = p.parse_args(argv)

    if args.cmd == "run":
        from .runner import run
        run(_run_cfg_from_args(args))
    elif args.cmd == "dashboard":
        from .dashboard import build_dashboard
        build_dashboard(args.runs, output_dir=args.output_dir, out=args.out)
    elif args.cmd == "ablate":
        from .ablation import run_suite
        run_suite(args.suite, model=args.model, subset=args.subset, provider=args.provider)


if __name__ == "__main__":
    main()
