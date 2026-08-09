# --- The sweep. One server at a time, hard time boxes, checkpointed to disk. ---
from agentverif.analysers import PYLINT_DISABLE, RUFF_SELECT
from agentverif.study import REPAIR_ROUNDS, run_study


def make_chat(model):
    """Adapt the OpenAI-compatible endpoint to the (reply, tokens) contract the
    study is written against.

    _post already turns a 4xx into a message carrying vLLM's own explanation, so
    the reason reaches the record rather than dying inside an unread response body.

    A 4xx is not retried: the server rejects the identical request the same way,
    so a retry only doubles the time spent failing. The one retry is for transient
    faults, which is all it was ever for.
    """
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
                if "HTTP 4" in str(exc):
                    raise
                last = exc
                if attempt == 0:
                    time.sleep(3)
        raise RuntimeError(f"{type(last).__name__}: {last}")
    return chat


def failure_signature(text):
    """The last exception line, which is what distinguishes a model problem from
    an environment problem. Four models failing on the same missing shared library
    is one fact repeated four times, not four findings."""
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    for ln in reversed(lines):
        if "Error" in ln or "error" in ln:
            return ln[:200]
    return lines[-1][:200] if lines else ""


sweep_started = time.time()
runs = []
seen_failures = set()

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
        try:
            proc, log_path = start_server(model)
        except Exception as exc:
            # A model-specific failure is worth moving past: Qwen once failed to
            # load on a machine where DeepSeek loaded fine minutes later. The same
            # failure twice is not model-specific, it is the environment, and
            # repeating it down the whole list buries the one error worth reading.
            sig = failure_signature(exc)
            repeat = sig and sig in seen_failures
            seen_failures.add(sig)
            print(f"  SERVER FAILED TO START:\n{exc}" if not repeat
                  else f"  SERVER FAILED TO START, same error as before: {sig}")
            runs.append({**model, "status": "failed: no_server", "tasks": 0,
                         "error": str(exc)[-1500:]})
            if repeat and not any(r["status"] == "ok" for r in runs):
                raise SystemExit(
                    f"\nTwo models failed identically and none has served:\n\n"
                    f"  {sig}\n\n"
                    "That is the environment, not the models, so the remaining "
                    "ones are not attempted. Fix it and re-run this cell - it "
                    f"resumes from {STEPS_PATH} rather than starting over."
                )
            continue

        load_min = (time.time() - load_started) / 60
        counters = run_study(TASKS, make_chat(model), model["short"], STEPS_PATH,
                            workers=WORKERS, time_budget_s=budget)
        runs.append({**model, "load_min": round(load_min, 1), **counters,
                     "status": "aborted" if counters["abort_reason"] else "ok"})
    except SystemExit:
        stop_server(proc)
        raise
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
# Whatever went wrong, print it here rather than leaving it in the scrollback.
for r in runs:
    if r.get("abort_reason") or r.get("last_error") or r.get("error"):
        print(f"\n{r['short']}: {r.get('abort_reason') or r.get('last_error') or ''}")
        if r.get("error"):
            print(r["error"])

with open(os.path.join(OUT_DIR, "run_manifest.json"), "w") as fh:
    json.dump({"commit": COMMIT, "branch": BRANCH,
               "seed": SEED, "n_tasks": len(TASKS), "n_tasks_requested": N_TASKS,
               "task_ids": [t.task_id for t in TASKS], "temperature": TEMPERATURE,
               "max_gen_tokens": MAX_GEN_TOKENS, "workers": WORKERS,
               "tensor_parallel": TP, "dtype": DTYPE,
               "max_model_len": MAX_MODEL_LEN, "max_num_seqs": MAX_NUM_SEQS,
               "analyser_versions": TOOL_VERSIONS,
               "ruff_select": RUFF_SELECT, "pylint_disable": PYLINT_DISABLE,
               "repair_rounds": REPAIR_ROUNDS,
               "runs": runs}, fh, indent=2)
