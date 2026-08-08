# --- The sweep. One server at a time, hard time boxes, checkpointed to disk. ---
from agentverif.analysers import PYLINT_DISABLE, RUFF_SELECT
from agentverif.study import REPAIR_ROUNDS, run_study


def make_chat(model):
    """Adapt the OpenAI-compatible endpoint to the (reply, tokens) contract the
    study is written against. One retry: at 32 concurrent requests a transient
    failure would otherwise cost a whole task's record, and a retry costs a few
    seconds."""
    def chat(prompt):
        payload = {"model": model["short"],
                   "messages": [{"role": "user", "content": prompt}],
                   "temperature": TEMPERATURE, "max_tokens": MAX_GEN_TOKENS}
        last = None
        for attempt in range(2):
            try:
                r = _post("/chat/completions", payload, timeout=900)
                return (r["choices"][0]["message"]["content"] or "",
                        (r.get("usage") or {}).get("completion_tokens", 0))
            except Exception as exc:
                last = exc
                if attempt == 0:
                    time.sleep(3)
        raise last
    return chat


sweep_started = time.time()
runs = []

for i, model in enumerate(MODELS):
    elapsed = time.time() - sweep_started
    left = TOTAL_BUDGET_S - elapsed
    # Split what is left evenly across the models still to come, rather than
    # letting the first model spend the whole budget. Loading time comes out of
    # the same pot, so a slow download shortens its own model's run and not the
    # ones after it.
    budget = min(PER_MODEL_BUDGET_S, left / (len(MODELS) - i))

    print(f"\n{'=' * 72}\n[{i + 1}/{len(MODELS)}] {model['family']}  {model['hf']}")
    print(f"{elapsed / 60:.0f} min elapsed, {left / 60:.0f} min left, "
          f"this model gets up to {budget / 60:.0f} min of generation")

    if budget < MIN_USEFUL_BUDGET_S:
        print("  skipped: not enough budget left to produce a usable sample")
        runs.append({**model, "status": "skipped_no_budget", "tasks": 0})
        continue

    proc = None
    try:
        load_started = time.time()
        proc, log_path = start_server(model)
        load_min = (time.time() - load_started) / 60
        counters = run_study(TASKS, make_chat(model), model["short"], STEPS_PATH,
                            workers=WORKERS, time_budget_s=budget)
        runs.append({**model, "status": "ok", "load_min": round(load_min, 1),
                     **counters})
    except Exception as exc:
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        runs.append({**model, "status": f"failed: {type(exc).__name__}", "tasks": 0})
    finally:
        stop_server(proc)
        free_weights(model)   # ~15GB each; the disk does not hold four

print(f"\n{'=' * 72}\nsweep finished in {(time.time() - sweep_started) / 3600:.2f}h")
print(f"{'model':24s} {'status':12s} {'load':>6s} {'tasks':>7s} {'steps':>7s} {'errors':>7s}")
for r in runs:
    print(f"{r['short']:24s} {r['status'][:12]:12s} {r.get('load_min', 0):>6} "
          f"{r.get('tasks', 0):>7} {r.get('steps', 0):>7} {r.get('errors', 0):>7}")

with open(os.path.join(OUT_DIR, "run_manifest.json"), "w") as fh:
    json.dump({"commit": COMMIT, "branch": BRANCH,
               "seed": SEED, "n_tasks": N_TASKS, "temperature": TEMPERATURE,
               "max_gen_tokens": MAX_GEN_TOKENS, "workers": WORKERS,
               "tensor_parallel": TP, "dtype": "float16",
               "analyser_versions": TOOL_VERSIONS,
               "ruff_select": RUFF_SELECT, "pylint_disable": PYLINT_DISABLE,
               "repair_rounds": REPAIR_ROUNDS,
               "runs": runs}, fh, indent=2)
