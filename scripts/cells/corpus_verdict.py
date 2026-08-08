# --- Verdict: is this corpus usable, and what does the run cost? ---
TARGET_ANALYSABLE = 150     # from the power calculation, not a guess
TOKENS_PER_ROUND = 600      # conservative; smoke test saw 40-175 on short prompts
# Sum of 1/throughput across the four measured models, in GPU-seconds per token.
SECONDS_PER_TOKEN_ALL_MODELS = 1 / 789 + 1 / 271 + 1 / 546 + 1 / 487

runnable_rate = len(runnable) / len(exec_results) if exec_results else 0.0

print(f"reference solutions that run here : {runnable_rate:.0%}")
for name in RULE_SETS:
    print(f"tasks with >=1 finding [{name:12s}]: {hit_rates[name]:.0%}")

# Pick the rule set that gives a workable hit rate without drowning the agent in
# trivia. Too low and screening cost explodes; too high and the findings are
# mostly formatting noise that says nothing about defects.
choice = None
for name in RULE_SETS:
    if 0.35 <= hit_rates[name] <= 0.95:
        choice = name
        break
if choice is None:
    choice = max(hit_rates, key=lambda k: hit_rates[k])

hit = hit_rates[choice]
print(f"\nselected rule set: {choice}  ({RULE_SETS[choice]})")

if runnable_rate < 0.5:
    print("\nSTOP. Fewer than half the reference solutions run here, so correctness")
    print("cannot be measured for most of the corpus. Run the fallback cell.")
elif hit < 0.15:
    print(f"\nSTOP. Only {hit:.0%} of tasks carry a finding even at the broadest rule")
    print("set, so screening would dominate the budget. Run the fallback cell, or")
    print("widen the rule selection before proceeding.")
else:
    # Screening: generate once per task, keep those with a finding AND a runnable
    # test. Repair rounds are spent only on survivors.
    usable_rate = max(hit * runnable_rate, 1e-6)
    to_screen = TARGET_ANALYSABLE / usable_rate
    rounds = to_screen * 1 + TARGET_ANALYSABLE * 4   # 1 screen + 2 ruff + 2 semgrep
    gpu_seconds = rounds * TOKENS_PER_ROUND * SECONDS_PER_TOKEN_ALL_MODELS
    overhead_min = 10 + 4 * 5                        # install plus four model loads

    print(f"\nTo reach {TARGET_ANALYSABLE} analysable tasks:")
    print(f"  usable share            {usable_rate:.0%}  (has a finding AND runs)")
    print(f"  tasks to screen         {to_screen:,.0f}")
    print(f"  generation rounds       {rounds:,.0f} per model set")
    print(f"  GPU time                {gpu_seconds / 3600:.1f} h")
    print(f"  plus overhead           {overhead_min} min")
    print(f"  TOTAL                   {gpu_seconds / 3600 + overhead_min / 60:.1f} h")

    if to_screen > len(records):
        print(f"\n  ! Needs {to_screen:,.0f} tasks but the corpus has {len(records)}.")
        print(f"    Lower the target or widen the rule set.")

    cpu_min = to_screen * (elapsed / len(exec_results)) / 60
    print(f"\n  CPU-side test execution adds roughly {cpu_min:.0f} min, overlappable "
          f"with generation.")

summary = {
    "corpus": CORPUS_ID, "n_tasks": len(records), "sample": len(exec_results),
    "runnable_rate": runnable_rate, "hit_rates": hit_rates,
    "selected_rule_set": choice, "assembly": best_strategy,
    "secs_per_task_exec": elapsed / len(exec_results) if exec_results else None,
    "semgrep_available": any(r["semgrep"] >= 0 for r in rows),
}
os.makedirs("/kaggle/working", exist_ok=True)
with open("/kaggle/working/corpus_check.json", "w") as fh:
    json.dump({"summary": summary, "rows": rows, "exec": exec_results}, fh, indent=2)
print("\nWrote /kaggle/working/corpus_check.json")
