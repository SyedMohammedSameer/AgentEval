# --- The corpus: fixed order, then filtered to tasks this machine can run. ---
# Shuffling once with a fixed seed and taking a prefix means any partial run is a
# uniform random sample rather than a biased slice of easy-first task ids, and it
# means the four models' task sets are nested rather than disjoint, so a
# cross-model comparison can be made paired on the tasks all of them reached.
#
# Then every candidate's *reference* solution is executed and only the ones that
# pass are kept. BigCodeBench is library-heavy and a missing package makes its
# tests fail with ModuleNotFoundError no matter what the model wrote, which would
# be scored as the agent breaking working code. Filtering on the reference makes a
# missing package cost coverage instead of corrupting the correctness result.
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from datasets import load_dataset

from agentverif.harness import Task, run_tests

ds = load_dataset("bigcode/bigcodebench", "default")
split = list(ds.keys())[0]
records = ds[split]

order = list(range(len(records)))
random.Random(SEED).shuffle(order)
candidates = [Task.from_record(records[i]) for i in order[:N_TASKS * 2]]
print(f"{len(records)} tasks in {split}; probing {len(candidates)} to find "
      f"{N_TASKS} runnable ones (seed {SEED})")

t0 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    probes = list(pool.map(lambda t: run_tests(t, t.reference_solution()), candidates))

TASKS, rejected, missing = [], Counter(), Counter()
for task, r in zip(candidates, probes):     # pool.map preserves order, so the
    if r.passed:                            # selection stays deterministic
        if len(TASKS) < N_TASKS:
            TASKS.append(task)
    else:
        rejected[r.kind] += 1
        if r.kind == "import_error":
            for word in r.detail.replace("'", " ").split():
                if word not in ("No", "module", "named", "import_error:",
                                "ModuleNotFoundError:"):
                    missing[word] += 1
                    break

print(f"probed in {(time.time() - t0) / 60:.1f} min: {len(TASKS)} kept, "
      f"{sum(rejected.values())} rejected {dict(rejected)}")
if missing:
    print("missing packages (install these to raise coverage):",
          " ".join(f"{p}({n})" for p, n in missing.most_common(12)))

if len(TASKS) < N_TASKS:
    print(f"\nNOTE: only {len(TASKS)} runnable tasks found, short of {N_TASKS}. "
          "The study runs on what is here; n is reported honestly in the results.")
if len(TASKS) < min(50, N_TASKS):
    raise SystemExit(
        f"Only {len(TASKS)} tasks are runnable in this environment. That is too "
        "few to measure anything. Install the packages listed above and re-run "
        "this cell."
    )
print("first five:", [t.task_id for t in TASKS[:5]])
