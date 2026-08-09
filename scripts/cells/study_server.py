# --- vLLM lifecycle: launch, prove it generates, shut down. ---
import json, signal, socket, time, urllib.error, urllib.request

_json = json
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}/v1"

# Fork inside a notebook kernel that has already touched CUDA is a known way to
# deadlock a tensor-parallel worker. Spawn costs a few seconds per launch.
os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

# Tried in order until one serves. Level 0 is the fast path. Level 1 drops CUDA
# graph capture, and on a multi-GPU host the custom all-reduce kernel too, since
# cards without NVLink or peer-to-peer are where collectives break. Level 2 halves
# the context as well, which is what an engine-core failure looks like when it is
# really KV-cache pressure. One model failing to load while another loads fine on
# the same machine is model-specific, so it is worth three cheap attempts.
_MULTI = ["--disable-custom-all-reduce"] if TP > 1 else []
LAUNCH_LADDER = [
    ("default", [], None),
    ("eager", ["--enforce-eager"] + _MULTI, None),
    ("eager+half-context", ["--enforce-eager"] + _MULTI, MAX_MODEL_LEN // 2),
]
LAUNCH_TIMEOUT_S = 1200      # a model that has not loaded in 20 min will not


def _port_free(port=PORT):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _cmd(model, rung):
    # No --disable-log-requests: it was removed in vLLM 0.11 for an opt-in
    # --enable-log-requests, newer builds reject it, and probing for it cost a
    # whole launch cycle per model. Newer vLLM does not log requests by default.
    _label, extra_args, ctx = rung
    return [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model["hf"],
        "--served-model-name", model["short"],
        "--host", "127.0.0.1", "--port", str(PORT),
        # Measured in section 1: bfloat16 on Ampere and later, float16 on Turing,
        # which has no bfloat16 at all and hard-fails if asked for it.
        "--dtype", DTYPE,
        "--max-model-len", str(ctx or MAX_MODEL_LEN),
        "--gpu-memory-utilization", str(GPU_MEM_FRACTION),
        "--tensor-parallel-size", str(TP),
        "--max-num-seqs", str(MAX_NUM_SEQS),
    ] + extra_args


def _post(path, payload, timeout=600):
    """A 4xx carries vLLM's explanation in the response body, and that body is the
    only place the reason exists. Not reading it is how a run once recorded 200
    consecutive failures without printing why once."""
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _json.loads(r.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace").strip()[:500]
        raise RuntimeError(f"HTTP {exc.code} from vLLM: {body}") from None


def root_cause(log_text, chars=2500):
    """The engine-core child logs the real error and the API server then re-raises
    it, so a plain tail shows only the re-raise. Everything before the first
    `(APIServer` line is where the cause actually is."""
    head = log_text.split("(APIServer")[0].strip()
    return head[-chars:] if head else log_text[-chars:]


def generation_check(model):
    """Prove the server generates, at the settings the study will actually use.

    A `max_tokens=1` ping proves the port answers and nothing more. One run passed
    that check and then failed all 200 tasks, because the failure was in
    generation, not in the socket. This is the same request shape the study sends,
    so anything that will break the run breaks here instead - in seconds.
    """
    r = _post("/chat/completions", {
        "model": model["short"],
        "messages": [{"role": "user", "content":
                      "Write a Python function that adds two numbers. "
                      "Reply with a single code block."}],
        "temperature": TEMPERATURE, "max_tokens": min(256, MAX_GEN_TOKENS)},
        timeout=300)
    text = (r["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise RuntimeError("server returned an empty completion")
    return text


def _attempt(model, rung):
    label = rung[0]
    log_path = os.path.join(LOG_DIR, f"{model['short']}.{label}.log")
    log = open(log_path, "w")
    proc = subprocess.Popen(_cmd(model, rung), stdout=log,
                            stderr=subprocess.STDOUT, preexec_fn=os.setsid,
                            env=os.environ.copy())
    started = time.time()
    while True:
        if proc.poll() is not None:
            log.flush()
            raise RuntimeError(f"exited {proc.returncode}. Root cause "
                               f"(full log at {log_path}):\n{root_cause(open(log_path).read())}")
        try:
            _post("/chat/completions",
                  {"model": model["short"], "max_tokens": 1,
                   "messages": [{"role": "user", "content": "ping"}]}, timeout=20)
        except Exception:
            if time.time() - started > LAUNCH_TIMEOUT_S:
                stop_server(proc)
                raise RuntimeError(f"not ready in {LAUNCH_TIMEOUT_S}s\n"
                                   f"{root_cause(open(log_path).read())}")
            time.sleep(5)
            continue

        # Answering is not serving. Confirm it generates before committing the run.
        try:
            sample = generation_check(model)
        except Exception as exc:
            stop_server(proc)
            raise RuntimeError(f"loaded but cannot generate: {exc}")
        print(f"  ready in {(time.time() - started) / 60:.1f} min ({label}); "
              f"sample: {sample.splitlines()[0][:60]!r}")
        return proc, log_path


def start_server(model):
    if not _port_free():
        raise RuntimeError("port 8000 in use; run the shutdown cell")
    errors = []
    for n, rung in enumerate(LAUNCH_LADDER):
        if n:
            print(f"  retrying: {rung[0]}")
        try:
            return _attempt(model, rung)
        except Exception as exc:
            errors.append(f"[{rung[0]}] {exc}")
            subprocess.run("pkill -f vllm.entrypoints.openai.api_server", shell=True)
            time.sleep(10)
    raise RuntimeError("every launch configuration failed:\n\n" + "\n\n".join(errors))


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
