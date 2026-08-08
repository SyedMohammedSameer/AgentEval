# --- Analysis. Offline over the checkpoint, so it can be re-derived without a GPU. ---
from agentverif.report import (collect_fates, common_tasks, correctness_shift,
                               format_headline, headline, load_steps, restrict,
                               suppression_directives, traded_defects)

steps = load_steps(STEPS_PATH)
if not steps:
    # Every model failed or was skipped. Say so plainly rather than raising a
    # FileNotFoundError that reads like a bug in the analysis.
    raise SystemExit(
        f"No steps at {STEPS_PATH}. The sweep produced nothing - check the "
        f"status column in section 8 and the server logs in {LOG_DIR}."
    )

models = sorted({s["model"] for s in steps})
print(f"{len(steps)} steps, {len(models)} models: {', '.join(models)}")

n_by_model = {m: len({s["task_id"] for s in steps
                      if s["model"] == m and s["arm"] == "baseline"
                      and not s.get("error")})
              for m in models}
shared = common_tasks(steps)
print("tasks completed:", n_by_model)
print(f"shared by all models: {len(shared)}")

print("\n" + "=" * 96)
print("HEADLINE  of the findings an agent removed from the analyser it was shown,")
print("          how many were still reported by the held-out twin it never saw")
print("=" * 96)
print(format_headline(headline(steps)))

print("\npooled across models, on the tasks all of them reached")
print(format_headline(headline(restrict(steps, shared), by_model=False)))

print("\n" + "=" * 96)
print("CORRECTNESS  a finding removed by breaking the function is not a fix")
print("=" * 96)
print(f"{'model':24s} {'arm':14s} {'n':>5s} {'pass before':>12s} {'pass after':>11s} "
      f"{'broke':>7s} {'repaired':>9s}")
for r in correctness_shift(steps):
    print(f"{r['model']:24s} {r['arm']:14s} {r['n']:>5d} {r['pass_before']:>12d} "
          f"{r['pass_after']:>11d} {r['broke']:>7d} {r['repaired']:>9d}")

print("\n" + "=" * 96)
print("MECHANISM  suppression directives the agent actually wrote")
print("=" * 96)
rows = suppression_directives(steps)
if rows:
    tools = sorted({k for r in rows for k in r if k not in ("model", "arm")})
    print(f"{'model':24s} {'arm':14s} " + " ".join(f"{t:>9s}" for t in tools))
    for r in rows:
        print(f"{r['model']:24s} {r['arm']:14s} "
              + " ".join(f"{r.get(t, 0):>9d}" for t in tools))
else:
    print("none written")

print("\n" + "=" * 96)
print("TRADES  codes present after repair that were absent before")
print("=" * 96)
trades = traded_defects(steps)
for code, n in list(trades.items())[:25]:
    print(f"  {code:24s} {n:>5d}")
if not trades:
    print("  none")

# Everything the write-up needs, saved next to the raw steps so the analysis can
# be redone or re-sliced by severity without another GPU hour.
summary = {
    "n_steps": len(steps),
    "tasks_by_model": n_by_model,
    "shared_tasks": sorted(shared),
    "headline_by_model": headline(steps),
    "headline_pooled_shared": headline(restrict(steps, shared), by_model=False),
    "correctness": correctness_shift(steps),
    "directives": suppression_directives(steps),
    "trades": trades,
    "fates": [vars(f) | {"transferred": f.transferred} for f in collect_fates(steps)],
}
with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2, default=str)
print(f"\nwrote {OUT_DIR}/summary.json and {STEPS_PATH}")
print("Download the whole results/ folder from the notebook output before the "
      "session expires.")
