# --- Load each model, measure it properly, shut it down. ---
# Throughput is swept across concurrency levels rather than sampled at one
# arbitrary batch size. A single measurement cannot tell you whether the GPUs are
# saturated or whether throughput was still climbing, and that difference sets
# the entire compute budget for the study.
#
# Per-GPU utilisation is sampled during each sweep point. Tensor parallelism is
# required here for memory reasons (7-9B at float16 does not fit one 16GB card),
# but "both GPUs are in use" and "both GPUs are busy" are different claims, and
# only the second one is worth anything. An imbalanced pair shows up here.
import threading
from concurrent.futures import ThreadPoolExecutor


def sample_gpu_utilisation(stop_event, samples, interval=0.5):
    """Poll per-GPU utilisation until told to stop."""
    while not stop_event.is_set():
        raw = _smi("index,utilization.gpu,memory.used")
        row = {}
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                row[parts[0]] = (int(parts[1].split()[0]), int(parts[2].split()[0]))
        if row:
            samples.append(row)
        time.sleep(interval)


def timed_batch(model, concurrency):
    """Run `concurrency` completions at once; return throughput and GPU busyness."""
    def one(i):
        return _post("/chat/completions", {
            "model": model["short"],
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": GEN_TOKENS, "temperature": 0.8, "seed": i})

    samples, stop = [], threading.Event()
    watcher = threading.Thread(target=sample_gpu_utilisation, args=(stop, samples), daemon=True)
    watcher.start()
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            outs = list(pool.map(one, range(concurrency)))
    finally:
        stop.set()
        watcher.join(timeout=3)

    elapsed = time.time() - t0
    completion_tokens = sum(o["usage"]["completion_tokens"] for o in outs)

    # Mean utilisation per GPU across the run, so an idle second card is visible.
    per_gpu = {}
    if samples:
        for idx in samples[0]:
            utils = [s[idx][0] for s in samples if idx in s]
            mems = [s[idx][1] for s in samples if idx in s]
            per_gpu[idx] = {"mean_util_pct": round(sum(utils) / len(utils)),
                            "peak_mem_mb": max(mems)}
    return {
        "concurrency": concurrency,
        "secs": round(elapsed, 1),
        "completion_tok_s": round(completion_tokens / elapsed),
        "per_gpu": per_gpu,
    }


results = []

for model in MODELS:
    print("\n" + "=" * 74)
    print(f"{model['family']}: {model['hf']}")
    print("=" * 74, flush=True)

    row = {"family": model["family"], "model": model["short"], "hf": model["hf"],
           "loaded": False, "note": ""}
    proc = None
    t0 = time.time()
    try:
        proc, log_path = start_server(model)
        row["loaded"] = True
        row["load_min"] = round((time.time() - t0) / 60, 1)

        # One completion kept verbatim: the question is whether the model's own
        # chat template produced usable code, not how good the code is.
        single = _post("/chat/completions", {
            "model": model["short"],
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": GEN_TOKENS, "temperature": 0.0})
        text = single["choices"][0]["message"]["content"]
        row["sample"] = text
        row["has_code_block"] = "```" in text
        first = text.strip().splitlines()[0][:90] if text.strip() else "(empty)"
        print(f"  template OK, code block: {row['has_code_block']}   first line: {first}")

        # Warm up and discard. The first batch absorbs CUDA graph capture and
        # cache warmup, which lands entirely on whichever sweep point runs first
        # and makes it look catastrophically slow. Measured on Qwen: 29 tok/s at
        # concurrency 8 followed by 293 at concurrency 16, purely from warmup.
        print("  warming up (discarded)...", flush=True)
        timed_batch(model, min(CONCURRENCY_SWEEP))

        # Sweep concurrency to find where throughput stops climbing.
        sweep = []
        for c in CONCURRENCY_SWEEP:
            point = timed_batch(model, c)
            sweep.append(point)
            gpus = "  ".join(f"gpu{i}:{v['mean_util_pct']}%/{v['peak_mem_mb']}MiB"
                             for i, v in sorted(point["per_gpu"].items()))
            print(f"  concurrency {c:3d} -> {point['completion_tok_s']:5d} tok/s "
                  f"in {point['secs']:5.1f}s   {gpus}")
        row["sweep"] = sweep

        best = max(sweep, key=lambda p: p["completion_tok_s"])
        row["completion_tok_s"] = best["completion_tok_s"]
        row["best_concurrency"] = best["concurrency"]
        row["per_gpu"] = best["per_gpu"]

        # Still climbing at the top of the sweep means the sweep, not the
        # hardware, was the limit, and the real study should push concurrency
        # higher than we tested.
        row["saturated"] = best["concurrency"] != CONCURRENCY_SWEEP[-1]
        utils = [v["mean_util_pct"] for v in best["per_gpu"].values()]
        row["min_gpu_util"] = min(utils) if utils else -1
        row["gpu_balanced"] = (max(utils) - min(utils) <= 20) if len(utils) > 1 else True

        print(f"  best: {row['completion_tok_s']} tok/s at concurrency "
              f"{row['best_concurrency']}"
              f"{'' if row['saturated'] else ' (still climbing, sweep was the limit)'}")
        if not row["gpu_balanced"]:
            print(f"  ! GPUs imbalanced: {utils} percent. Tensor parallelism is not "
                  f"splitting the work evenly.")

    except Exception as exc:
        row["note"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAILED: {row['note']}"[:800])
    finally:
        stop_server(proc)
        free_weights(model)

    results.append(row)

print("\nall models attempted")
