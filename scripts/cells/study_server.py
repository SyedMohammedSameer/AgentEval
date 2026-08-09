# --- vLLM lifecycle: launch, wait until it truly answers, shut down. ---
import json, signal, socket, time, urllib.error, urllib.request

_json = json
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}/v1"

# Tried in order until one serves. Level 0 is the fast path. Level 1 turns off
# the two things most likely to break tensor-parallel on a pair of T4s, which
# have no NVLink and no peer-to-peer: CUDA graph capture and the custom
# all-reduce kernel. Level 2 additionally halves the context, which is what an
# engine-core failure looks like when it is really KV-cache pressure.
# One model failing to load while another loads fine on the same machine is a
# model-specific problem, so it is worth three cheap attempts before giving up.
LAUNCH_LADDER = [
    ("as configured", [], None),
    ("eager, no custom all-reduce", ["--enforce-eager", "--disable-custom-all-reduce"], None),
    ("eager, no custom all-reduce, 4k context",
     ["--enforce-eager", "--disable-custom-all-reduce"], 4096),
]


def _port_free(port=PORT):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _cmd(model, rung, extras=True):
    """Required args, the rung's fallback flags, plus one cosmetic flag.

    `--disable-log-requests` was removed in vLLM 0.11 in favour of an opt-in
    `--enable-log-requests`, so newer releases reject it. It is the only flag in
    the optional set: `--max-num-seqs` controls batching and has been stable for
    years, so dropping it as collateral for a rejected cosmetic flag would
    quietly cost throughput for the whole run.
    """
    _label, extra_args, ctx = rung
    return [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model["hf"],
        "--served-model-name", model["short"],
        "--host", "127.0.0.1", "--port", str(PORT),
        # T4 has no bfloat16; several of these configs request it by default.
        "--dtype", "float16",
        "--max-model-len", str(ctx or MAX_MODEL_LEN),
        "--gpu-memory-utilization", str(GPU_MEM_FRACTION),
        "--tensor-parallel-size", str(TP),
        "--max-num-seqs", str(MAX_NUM_SEQS),
    ] + extra_args + (["--disable-log-requests"] if extras else [])


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read())


def root_cause(log_text, chars=2500):
    """The engine-core child logs the real error and the API server then re-raises
    it, so a plain tail shows only the re-raise. Everything before the first
    `(APIServer` line is where the cause actually is."""
    head = log_text.split("(APIServer")[0].strip()
    return head[-chars:] if head else log_text[-chars:]


def _attempt(model, rung, extras, timeout_s):
    """One launch. Ready means 'returned a completion', not '/health answered':
    the endpoint accepts connections before weights finish loading, so health
    alone would let a run start early and fail every request at once."""
    label = rung[0]
    suffix = label.split(",")[0].replace(" ", "_")
    log_path = os.path.join(LOG_DIR, f"{model['short']}.{suffix}.log")
    log = open(log_path, "w")
    proc = subprocess.Popen(_cmd(model, rung, extras), stdout=log,
                            stderr=subprocess.STDOUT, preexec_fn=os.setsid,
                            env=os.environ.copy())
    started = time.time()
    while True:
        if proc.poll() is not None:
            log.flush()
            text = open(log_path).read()
            if extras and ("unrecognized arguments" in text or "invalid choice" in text):
                print("    --disable-log-requests rejected by this vLLM; dropping it")
                return _attempt(model, rung, False, timeout_s)
            raise RuntimeError(f"exited {proc.returncode}. Root cause "
                               f"(full log at {log_path}):\n{root_cause(text)}")
        try:
            _post("/chat/completions",
                  {"model": model["short"], "max_tokens": 1,
                   "messages": [{"role": "user", "content": "ping"}]}, timeout=20)
            print(f"  ready in {(time.time() - started) / 60:.1f} min ({label})")
            return proc, log_path
        except Exception:
            pass
        if time.time() - started > timeout_s:
            stop_server(proc)
            raise RuntimeError(f"not ready in {timeout_s}s\n"
                               f"{root_cause(open(log_path).read())}")
        time.sleep(5)


def start_server(model, timeout_s=2400):
    if not _port_free():
        raise RuntimeError("port 8000 in use; run the shutdown cell")
    errors = []
    for n, rung in enumerate(LAUNCH_LADDER):
        if n:
            print(f"  retrying: {rung[0]}")
        try:
            return _attempt(model, rung, True, timeout_s)
        except Exception as exc:
            errors.append(f"[{rung[0]}] {exc}")
            if not _port_free():
                subprocess.run("pkill -f vllm.entrypoints.openai.api_server",
                               shell=True)
                time.sleep(10)
    raise RuntimeError("every launch configuration failed:\n\n"
                       + "\n\n".join(errors))


def stop_server(proc):
    if proc is None or proc.poll() is not None:
        return
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    try:
        proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=30)
    time.sleep(5)   # let the GPUs actually free before the next load


def free_weights(model):
    """~15GB per model; the scratch disk does not hold four."""
    import shutil
    slug = "models--" + model["hf"].replace("/", "--")
    for root in (os.path.join(HF_CACHE, "hub"), HF_CACHE):
        p = os.path.join(root, slug)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)


print("helpers ready")
