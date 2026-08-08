# --- The corpus, in the one fixed order every model will walk. ---
# Shuffling once with a fixed seed and taking a prefix means any partial run is a
# uniform random sample rather than a biased slice of easy-first task ids, and it
# means the four models' task sets are nested rather than disjoint, so a
# cross-model comparison can be made paired on the tasks all of them reached.
import random

from datasets import load_dataset

from agentverif.harness import Task

ds = load_dataset("bigcode/bigcodebench", "default")
split = list(ds.keys())[0]
records = ds[split]

order = list(range(len(records)))
random.Random(SEED).shuffle(order)
TASKS = [Task.from_record(records[i]) for i in order[:N_TASKS]]

print(f"{len(records)} tasks in {split}; using {len(TASKS)} (seed {SEED})")
print("first five:", [t.task_id for t in TASKS[:5]])

# The reference solution must actually run here, or a failing test tells us
# nothing about the model. The corpus check measured 92%; this confirms the same
# environment before any GPU time is spent.
from agentverif.harness import run_tests

probe = [run_tests(t, t.reference_solution()) for t in TASKS[:12]]
ok = sum(r.passed for r in probe)
print(f"\nreference solutions passing: {ok}/12")
for t, r in zip(TASKS[:12], probe):
    if not r.passed:
        print(f"  {t.task_id}: {r.detail[:90]}")
if ok < 8:
    raise SystemExit(
        "Reference solutions are failing at a rate that would confound the "
        "correctness measurement. Stop and fix the environment first."
    )
