# --- Load the corpus and learn its schema rather than assume it. ---
# The exact field names of BigCodeBench are not something to take on trust, so
# this prints them and every later cell builds against what is actually there.
import json
import os
import random
import subprocess
import sys
import tempfile
import textwrap
import time

CORPUS_ID = "bigcode/bigcodebench"
SAMPLE_N = 60          # tasks to actually execute; enough to estimate rates
EXEC_TIMEOUT = 25      # seconds per task
WORKERS = max(2, (os.cpu_count() or 4))
SEED = 0

try:
    from datasets import get_dataset_config_names, load_dataset
except ImportError:
    subprocess.run("pip install -q datasets", shell=True, check=True)
    from datasets import get_dataset_config_names, load_dataset

configs = []
try:
    configs = get_dataset_config_names(CORPUS_ID)
    print(f"configs: {configs}")
except Exception as exc:
    print(f"could not list configs: {type(exc).__name__}: {exc}")

ds = None
for attempt in ([configs[-1]] if configs else []) + [None, "default"]:
    try:
        ds = load_dataset(CORPUS_ID, attempt) if attempt else load_dataset(CORPUS_ID)
        print(f"loaded with config={attempt!r}")
        break
    except Exception as exc:
        print(f"  config={attempt!r} failed: {type(exc).__name__}: {str(exc)[:120]}")

if ds is None:
    raise SystemExit(
        "Could not load BigCodeBench. Run the fallback cell at the bottom, which "
        "uses EvalPlus instead."
    )

split = list(ds.keys())[0]
records = ds[split]
print(f"\nsplit {split!r}: {len(records)} tasks")

FIELDS = list(records[0].keys())
print(f"\nfields: {FIELDS}")
for f in FIELDS:
    val = records[0][f]
    preview = str(val).replace("\n", " ")[:90]
    print(f"  {f:22s} {type(val).__name__:6s} {preview}")

# Fixed shuffle: every later cell, and any future extension run, draws from the
# same order, so a partial run is a uniform random sample rather than a biased
# prefix.
order = list(range(len(records)))
random.Random(SEED).shuffle(order)
print(f"\nshuffled with seed {SEED}; first ids: {[records[i].get('task_id') for i in order[:5]]}")
