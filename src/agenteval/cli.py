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
        seed=a.seed,
        output_dir=a.output_dir,
    )


def _parse_seeds(spec: str) -> list[int]:
    """`3` -> [0,1,2] (a count), `0,7,42` -> those exact seeds (a list)."""
    if "," in spec:
        return [int(s) for s in spec.split(",") if s.strip()]
    n = int(spec)
    if n < 1:
        raise SystemExit("--seeds must be >= 1")
    return list(range(n))


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
    r.add_argument("--seed", type=int, default=0, help="base sampling seed")
    r.add_argument("--output-dir", default="results")

    d = sub.add_parser("dashboard", help="render an HTML report over one or more runs")
    d.add_argument("runs", nargs="*", help="run names under results/ (default: all)")
    d.add_argument("--output-dir", default="results")
    d.add_argument("--out", default="results/dashboard.html")

    a = sub.add_parser("ablate", help="run a predefined ablation sweep")
    a.add_argument("--suite", default="core", help="ablation suite name (see src/agenteval/ablation.py)")
    a.add_argument("--model", default="qwen2.5-coder:7b")
    a.add_argument("--subset", default="smoke")
    a.add_argument("--provider", default="local")
    a.add_argument(
        "--seeds",
        default="1",
        help="replications per condition: a count (`3` => seeds 0,1,2) or an explicit list (`0,7,42`)",
    )
    a.add_argument("--output-dir", default="results")

    rep = sub.add_parser("report", help="re-print the pooled ablation table from existing runs")
    rep.add_argument("--suite", default=None, help="limit to one suite (default: all runs)")
    rep.add_argument("--output-dir", default="results")

    rc = sub.add_parser(
        "reclassify",
        help="re-apply the current failure taxonomy to saved trajectories (no model calls)",
    )
    rc.add_argument("runs", nargs="*", help="run names under results/ (default: all)")
    rc.add_argument("--output-dir", default="results")

    pw = sub.add_parser("power", help="how many tasks a sweep needs to detect an effect")
    pw.add_argument(
        "--effect", type=float, default=0.2,
        help="share of tasks the ablation is expected to break (0.33 = a very large effect)",
    )
    pw.add_argument("--power", type=float, default=0.8, help="target power")
    pw.add_argument("--tasks", type=int, default=None, help="instead: power of a given task count")

    args = p.parse_args(argv)

    if args.cmd == "run":
        from .runner import run
        run(_run_cfg_from_args(args))
    elif args.cmd == "dashboard":
        from .dashboard import build_dashboard
        build_dashboard(args.runs, output_dir=args.output_dir, out=args.out)
    elif args.cmd == "ablate":
        from .ablation import run_suite
        run_suite(
            args.suite,
            model=args.model,
            subset=args.subset,
            provider=args.provider,
            seeds=_parse_seeds(args.seeds),
            output_dir=args.output_dir,
        )
    elif args.cmd == "report":
        from .ablation import report
        report(args.suite, output_dir=args.output_dir)
    elif args.cmd == "reclassify":
        from .runner import reclassify
        reclassify(args.runs, output_dir=args.output_dir)
    elif args.cmd == "power":
        _power(args)


def _power(a) -> None:
    """Sample-size planning, so a sweep isn't launched at 18% power."""
    from .stats import min_discordant_for_significance, power_mcnemar, required_tasks

    floor = min_discordant_for_significance()
    print(f"Exact McNemar needs >= {floor} one-directional flips to reach p<0.05.\n")

    if a.tasks is not None:
        p = power_mcnemar(a.tasks, a.effect)
        print(f"n={a.tasks} tasks, effect={a.effect:.0%} of tasks flipping -> power {p:.0%}")
        if p < a.power:
            need = required_tasks(a.effect, target_power=a.power)
            print(f"Below the {a.power:.0%} target. Need ~{need} tasks." if need
                  else "Below target and >400 tasks required; the effect is too small to chase.")
        return

    need = required_tasks(a.effect, target_power=a.power)
    if need is None:
        print(f"effect={a.effect:.0%}: more than 400 tasks needed for {a.power:.0%} power.")
        return
    print(f"effect={a.effect:.0%} of tasks flipping -> ~{need} tasks for {a.power:.0%} power.")
    print("\nPower by task count at this effect size:")
    for n in (12, 20, 30, 40, 60, 100):
        print(f"  n={n:4d}   power={power_mcnemar(n, a.effect):.0%}")


if __name__ == "__main__":
    main()
