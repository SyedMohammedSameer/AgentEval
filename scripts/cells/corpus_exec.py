# --- Can the tests actually run here? ---
# Correctness measurement is not optional: without it, an agent that "fixes"
# findings by deleting the function looks like a success. So the corpus is only
# usable if its own reference solutions pass their own tests on this machine.
#
# BigCodeBench draws on a long tail of third-party libraries, and Kaggle's image
# will not have all of them. The number that matters is not "does it work" but
# "what share of tasks run", because that share is the real corpus size.
from concurrent.futures import ThreadPoolExecutor


def assemble(rec, strategy):
    """Build a runnable file from a record. Strategies are tried in order because
    the field layout is discovered at runtime rather than assumed."""
    g = rec.get
    if strategy == "prompt+canonical+test":
        head = g("complete_prompt") or g("code_prompt") or g("prompt") or ""
        return f"{head}\n{g('canonical_solution') or ''}\n\n{g('test') or ''}"
    if strategy == "canonical+test":
        return f"{g('canonical_solution') or ''}\n\n{g('test') or ''}"
    if strategy == "solution+test":
        return f"{g('solution') or ''}\n\n{g('test') or ''}"
    raise ValueError(strategy)


def make_runnable(source):
    """Append a unittest entry point when the test file relies on one."""
    if "unittest" in source and "__main__" not in source:
        source += "\n\nif __name__ == '__main__':\n    unittest.main(verbosity=0)\n"
    return source


def execute(source, timeout=EXEC_TIMEOUT):
    """Run a candidate file in its own process. Returns (ok, detail)."""
    d = tempfile.mkdtemp()
    path = os.path.join(d, "candidate.py")
    with open(path, "w") as fh:
        fh.write(make_runnable(source))
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=timeout, cwd=d)
        if r.returncode == 0:
            return True, "pass"
        tail = (r.stderr or r.stdout).strip().splitlines()
        last = tail[-1][:150] if tail else "no output"
        kind = "import_error" if "ModuleNotFoundError" in (r.stderr or "") else "fail"
        return False, f"{kind}: {last}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, f"harness_error: {type(exc).__name__}: {exc}"


# Pick the assembly strategy on a handful of tasks before spending the sample.
probe_ids = order[:6]
best_strategy, best_hits = None, -1
for strategy in ("prompt+canonical+test", "canonical+test", "solution+test"):
    try:
        hits = sum(execute(assemble(records[i], strategy))[0] for i in probe_ids)
    except Exception as exc:
        print(f"  {strategy:26s} unusable: {type(exc).__name__}: {exc}")
        continue
    print(f"  {strategy:26s} {hits}/{len(probe_ids)} reference solutions pass")
    if hits > best_hits:
        best_strategy, best_hits = strategy, hits

if best_hits <= 0:
    raise SystemExit(
        "No assembly strategy makes the reference solutions pass. The corpus "
        "cannot measure correctness here; run the fallback cell."
    )
print(f"\nusing strategy: {best_strategy}")

# Now measure the real runnable share on a proper sample.
sample_ids = order[:SAMPLE_N]
print(f"\nexecuting {len(sample_ids)} reference solutions on {WORKERS} workers...")

t0 = time.time()
def run_idx(i):
    rec = records[i]
    ok, detail = execute(assemble(rec, best_strategy))
    return {"idx": i, "task_id": rec.get("task_id"), "ok": ok, "detail": detail}

with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    exec_results = list(pool.map(run_idx, sample_ids))
elapsed = time.time() - t0

runnable = [r for r in exec_results if r["ok"]]
by_kind = {}
for r in exec_results:
    if not r["ok"]:
        kind = r["detail"].split(":")[0]
        by_kind[kind] = by_kind.get(kind, 0) + 1

print(f"\n{len(runnable)}/{len(exec_results)} reference solutions pass "
      f"({len(runnable) / len(exec_results):.0%})")
print(f"wall clock {elapsed:.0f}s for {len(sample_ids)} tasks "
      f"= {elapsed / len(sample_ids):.1f}s per task at {WORKERS} workers")
for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
    print(f"  {kind:16s} {n}")

for r in exec_results:
    if not r["ok"]:
        print(f"    e.g. {r['task_id']}: {r['detail'][:110]}")
        break
