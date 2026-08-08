# --- Verdict. ---
# A model can load and still fail during the throughput measurement, so "loaded"
# and "measured" are tracked separately. Conflating them crashes this cell on
# exactly the partial failure it exists to report.
import json as _json_out

print(f"{'family':10s} {'model':22s} {'load':5s} {'min':6s} {'tok/s':8s} {'GPU MiB':9s} note")
for r in results:
    print(f"{r['family']:10s} {r['model']:22s} "
          f"{'yes' if r['loaded'] else 'NO':5s} "
          f"{str(r.get('load_min', '-')):6s} "
          f"{str(r.get('completion_tok_s', '-')):8s} "
          f"{str(r.get('peak_gpu_mb', '-')):9s} {r['note'][:56]}")

loaded = [r for r in results if r["loaded"]]
measured = [r for r in loaded if "completion_tok_s" in r]

print(f"\n{len(loaded)}/{len(results)} models loaded, {len(measured)} fully measured")

for r in loaded:
    if "completion_tok_s" not in r:
        print(f"  ! {r['model']} loaded but throughput was not measured: {r['note'][:80]}")

if not measured:
    print("\nNo throughput measured, so there is no compute budget to plan against.")
    print("Read /kaggle/working/smoke-logs/*.log before changing anything: several")
    print("models failing the same way is usually one environment problem, not four")
    print("model problems.")
else:
    print("\n--- GPU usage ---")
    for r in measured:
        gpus = "  ".join(f"gpu{i}:{v['mean_util_pct']}%"
                         for i, v in sorted(r.get("per_gpu", {}).items()))
        flags = []
        if not r.get("gpu_balanced", True):
            flags.append("IMBALANCED")
        if not r.get("saturated", True):
            flags.append("still climbing at top of sweep")
        if r.get("min_gpu_util", 100) < 50:
            flags.append("a card is mostly idle")
        print(f"  {r['model']:22s} best concurrency {r.get('best_concurrency', '-'):>3}  "
              f"{gpus}  {'; '.join(flags)}")

    unsaturated = [r for r in measured if not r.get("saturated", True)]
    if unsaturated:
        print("\n  Throughput was still rising at the widest concurrency tested, so the")
        print("  sweep was the limit rather than the hardware. The real study should")
        print("  push concurrency past the top of this sweep and re-measure.")

    idle = [r for r in measured if r.get("min_gpu_util", 100) < 50]
    if idle:
        print("\n  At least one card sat below 50% on: "
              + ", ".join(r["model"] for r in idle))
        print("  Tensor parallelism is required here for memory reasons, but if a card")
        print("  is idle the split is not paying for its all-reduce cost. Worth")
        print("  comparing against two single-GPU servers on quantised weights.")

    slowest = min(r["completion_tok_s"] for r in measured)
    fastest = max(r["completion_tok_s"] for r in measured)
    # A repair-loop sample is roughly three rounds of ~400 completion tokens.
    per_sample_tokens = 3 * 400
    per_hour = slowest * 3600 / per_sample_tokens
    print(f"\nThroughput: {slowest}-{fastest} completion tok/s")
    print(f"At the slowest rate, ~{per_hour:,.0f} repair-loop samples per GPU-hour,")
    print(f"so 20 usable hours is on the order of {per_hour * 20:,.0f} samples.")
    if per_hour * 20 >= 10000:
        print("\nThat puts sample size well clear of being the binding constraint,")
        print("which is the property this design was chosen for.")
    else:
        print("\nThat is tighter than the design assumed. Scope the task set down")
        print("or the rounds, and re-check power before committing to a full run.")

if len(measured) < 4:
    print("\nFewer than four families measured. Substitute from the fallbacks before")
    print("running the study: a three-family result invites the objection that the")
    print("finding is specific to one lineage.")

with open("/kaggle/working/smoke_results.json", "w") as fh:
    _json_out.dump(results, fh, indent=2)
print("\nWrote /kaggle/working/smoke_results.json")
