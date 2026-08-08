# --- vLLM lifecycle: launch, wait until it truly answers, shut down. ---
import json, signal, socket, time, urllib.request

_json = json
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}/v1"


def _port_free(port=PORT):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _cmd(model, extras=True):
    """Required args, plus the one flag that is purely cosmetic.

    `--disable-log-requests` was removed in vLLM 0.11 in favour of an opt-in
    `--enable-log-requests`, and newer releases will reject it. It is the only
    flag in the optional set: `--max-num-seqs` has been stable for years and
    controls batching, so dropping it as collateral for a rejected cosmetic flag
    would quietly cost throughput for the whole run.
    """
    required = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model["hf"],
        "--served-model-name", model["short"],
        "--host", "127.0.0.1", "--port", str(PORT),
        # T4 has no bfloat16; several of these configs request it by default.
        "--dtype", "float16",
        "--max-model-len", str(MAX_MODEL_LEN),
        "--gpu-memory-utilization", str(GPU_MEM_FRACTION),
        "--tensor-parallel-size", str(TP),
        "--max-num-seqs", str(MAX_NUM_SEQS),
    ]
    return required + (["--disable-log-requests"] if extras else [])


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read())


def root_cause(log_text, chars=3000):
    """The engine-core child logs the real error; the API server then re-raises
    it, so a plain tail shows only the re-raise. Everything before the first
    `(APIServer` line is where the cause actually is."""
    head = log_text.split("(APIServer")[0].strip()
    return (head[-chars:] if head else log_text[-chars:])


def start_server(model, timeout_s=2400, extras=True):
    """Ready means 'returned a completion', not '/health answered'.

    The endpoint accepts connections before weights finish loading, so health
    alone would let a run start early and fail every request at once.
    """
    if not _port_free():
        raise RuntimeError("port 8000 in use; run the shutdown cell")

    # Suffixed so a retry cannot overwrite the failing attempt's log. Losing the
    # first attempt's output to the second attempt's is how this run had to be
    # diagnosed by hand.
    log_path = os.path.join(LOG_DIR, f"{model['short']}{'' if extras else '.noextras'}.log")
    log = open(log_path, "w")
    proc = subprocess.Popen(_cmd(model, extras), stdout=log,
                            stderr=subprocess.STDOUT, preexec_fn=os.setsid,
                            env=os.environ.copy())
    started = time.time()
    while True:
        if proc.poll() is not None:
            log.flush()
            text = open(log_path).read()
            if extras and ("unrecognized arguments" in text or "invalid choice" in text):
                print("  --disable-log-requests rejected by this vLLM; retrying without it")
                return start_server(model, timeout_s, extras=False)
            raise RuntimeError(
                f"vLLM exited {proc.returncode}. Root cause (full log at {log_path}):"
                f"\n--- engine core ---\n{root_cause(text)}")
        try:
            _post("/chat/completions", {"model": model["short"],
                                        "messages": [{"role": "user", "content": "ping"}],
                                        "max_tokens": 1}, timeout=20)
            print(f"  ready in {(time.time() - started) / 60:.1f} min")
            return proc, log_path
        except Exception:
            pass
        if time.time() - started > timeout_s:
            stop_server(proc)
            raise RuntimeError(f"not ready in {timeout_s}s\n{root_cause(open(log_path).read())}")
        time.sleep(5)


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
