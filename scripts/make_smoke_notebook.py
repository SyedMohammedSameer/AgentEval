"""Generate notebooks/00_smoke_test.ipynb.

Generated rather than hand-written so the JSON is always valid and the cell
sources stay reviewable as ordinary Python.

    python scripts/make_smoke_notebook.py

The smoke test answers, in about twenty minutes and before any real run:

  1. Do all four models load on 2xT4 under vLLM at float16 with tensor-parallel 2?
  2. What throughput do they reach under batch, which sets the whole compute budget?
  3. Does each model's own chat template get applied, and does it emit usable code?
  4. Do the static analysers install and run?

Every one of those is a run-ending surprise if discovered later.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "00_smoke_test.ipynb"


MD_INTRO = """\
# Smoke test: four model families on 2x T4

Verifies the experimental substrate before any GPU time is committed to a real run.
Takes roughly twenty minutes.

## Settings that must be right

**Accelerator: `GPU T4 x2`.** Not P100. vLLM needs CUDA compute capability 7.0 or
newer and the P100 is 6.0. The first cell checks and stops.

**Internet: ON** (Settings -> Internet), for pip and the model downloads.

## What it checks

| check | why it matters |
|---|---|
| each model loads | availability, gating, and sm75 compatibility are all assumed until proven |
| tokens/sec under batch | sets the compute budget for the whole study |
| peak GPU memory | tells us whether a larger tier is reachable later |
| native chat template | four families means four templates; a hand-rolled prompt would confound family with formatting |
| analysers run | the study measures their findings, so they are part of the substrate |

Nothing here produces a research result. It exists so the real run does not fail
four hours in.
"""

CELL_GPU = '''\
# --- Accelerator check: fail in seconds rather than mid-download. ---
import subprocess, sys

def _smi(fields):
    r = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""

raw = _smi("name,memory.total,compute_cap") or _smi("name,memory.total")
if not raw:
    raise SystemExit("No GPU. Set Accelerator to 'GPU T4 x2' in the settings panel.")

gpus = [line.split(", ") for line in raw.splitlines()]
for g in gpus:
    print("  " + " | ".join(g))

names = " ".join(g[0] for g in gpus).lower()
caps = [float(g[2]) for g in gpus if len(g) > 2]
if "p100" in names or (caps and min(caps) < 7.0):
    raise SystemExit(
        "\\nThis accelerator cannot run vLLM: it needs compute capability >= 7.0 "
        "and the P100 is 6.0. Switch to 'GPU T4 x2' (7.5)."
    )

N_GPUS = len(gpus)
print(f"\\nOK: {N_GPUS} GPU(s), compute capability {caps or 'unknown'}")
'''

CELL_INSTALL = '''\
# --- Install. ~5-10 min, mostly vLLM's dependencies. ---
# vLLM is only ever launched as a subprocess, so this kernel never imports torch
# and no kernel restart is needed.
import os

def sh(cmd, check=True):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {cmd}")
    return r.returncode

sh("pip install -q -U vllm")
# The analysers whose findings the study measures. Installed here so a missing
# wheel surfaces now rather than halfway through a sweep.
sh("pip install -q ruff bandit semgrep radon")

# Weights must not land in /kaggle/working: that is the saved output and is
# size-capped. Scratch instead.
HF_CACHE = "/kaggle/temp/hf" if os.path.isdir("/kaggle/temp") else "/tmp/hf"
os.makedirs(HF_CACHE, exist_ok=True)
os.environ["HF_HOME"] = HF_CACHE
print("\\nHF cache:", HF_CACHE)
'''

CELL_CONFIG = '''\
# ============================== CONFIGURATION ==============================
# Four families, four pretraining corpora, all code-specialised instruct models
# within a 1.3x size spread. All are Llama or Qwen2 architecture, which are the
# most exercised paths in vLLM and involve no exotic attention. All are ungated,
# so no license acceptance and no HF_TOKEN.
#
# float16 rather than AWQ on purpose: at this size the weights fit across two
# T4s with room for KV cache, and no quantisation kernels are involved at all,
# which removes the largest sm75 unknown.
MODELS = [
    {"hf": "Qwen/Qwen2.5-Coder-7B-Instruct",            "short": "qwen2.5-coder-7b",  "family": "Alibaba"},
    {"hf": "deepseek-ai/deepseek-coder-6.7b-instruct",  "short": "deepseek-coder-6.7b", "family": "DeepSeek"},
    {"hf": "01-ai/Yi-Coder-9B-Chat",                    "short": "yi-coder-9b",       "family": "01.AI"},
    {"hf": "ibm-granite/granite-8b-code-instruct-128k", "short": "granite-8b-code",   "family": "IBM"},
]

TP = min(2, N_GPUS)        # 7-9B at float16 does not fit one 16GB card
MAX_MODEL_LEN = 8192       # ample for the smoke prompts; the real run sets its own
GPU_MEM_FRACTION = 0.90
BATCH = 32                 # concurrent requests, to measure batched throughput
GEN_TOKENS = 256
LOG_DIR = "/kaggle/working/smoke-logs"
os.makedirs(LOG_DIR, exist_ok=True)
# ===========================================================================

# A prompt with a real, checkable answer: it must produce runnable Python, and
# the naive solution trips at least one analyser (subprocess with shell=True).
PROMPT = (
    "Write a Python function `run_command(cmd: str) -> str` that runs a shell "
    "command and returns its stdout as a string. Reply with only a Python code "
    "block, no explanation."
)

print(f"{len(MODELS)} models, tensor-parallel {TP}, batch {BATCH}")
for m in MODELS:
    print(f"  {m['family']:10s} {m['hf']}")
'''

CELL_SERVER = '''\
# --- vLLM lifecycle: launch, wait until it truly answers, shut down. ---
import json as _json, signal, socket, time, urllib.request

PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}/v1"


def _port_free(port=PORT):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _cmd(model, extras=True):
    """Required args, plus tuning flags worth retrying without.

    Every optional flag has been renamed or dropped in some vLLM release, and a
    run should not die because a tuning knob moved.
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
    ]
    return required + (["--max-num-seqs", str(BATCH), "--disable-log-requests"]
                       if extras else [])


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read())


def start_server(model, timeout_s=2400, extras=True):
    """Ready means 'returned a completion', not '/health answered'.

    The endpoint accepts connections before weights finish loading, so health
    alone would let a run start early and fail every request at once.
    """
    if not _port_free():
        raise RuntimeError("port 8000 in use; run the shutdown cell")

    log_path = os.path.join(LOG_DIR, f"{model['short']}.log")
    log = open(log_path, "w")
    proc = subprocess.Popen(_cmd(model, extras), stdout=log,
                            stderr=subprocess.STDOUT, preexec_fn=os.setsid,
                            env=os.environ.copy())
    started = time.time()
    while True:
        if proc.poll() is not None:
            log.flush()
            tail = open(log_path).read()[-4000:]
            if extras and ("unrecognized arguments" in tail or "invalid choice" in tail):
                print("  optional flag rejected; retrying with required args only")
                return start_server(model, timeout_s, extras=False)
            raise RuntimeError(f"vLLM exited {proc.returncode}\\n--- log tail ---\\n{tail}")
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
            raise RuntimeError(f"not ready in {timeout_s}s\\n{open(log_path).read()[-4000:]}")
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
    import shutil
    slug = "models--" + model["hf"].replace("/", "--")
    for root in (os.path.join(HF_CACHE, "hub"), HF_CACHE):
        p = os.path.join(root, slug)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)


def peak_gpu_mb():
    out = _smi("memory.used")
    return sum(int(x.split()[0]) for x in out.splitlines()) if out else -1


print("helpers ready")
'''

CELL_RUN = '''\
# --- Load each model, measure it, shut it down. ---
from concurrent.futures import ThreadPoolExecutor

results = []

for model in MODELS:
    print("\\n" + "=" * 70)
    print(f"{model['family']}: {model['hf']}")
    print("=" * 70, flush=True)

    row = {"family": model["family"], "model": model["short"], "hf": model["hf"],
           "loaded": False, "note": ""}
    proc = None
    t0 = time.time()
    try:
        proc, log_path = start_server(model)
        row["loaded"] = True
        row["load_min"] = round((time.time() - t0) / 60, 1)

        # 1. Architecture and template, straight from the server's own log.
        log = open(log_path).read()
        for key in ("architectures", "Chat template", "chat_template"):
            for line in log.splitlines():
                if key in line:
                    row.setdefault("log_notes", []).append(line.strip()[:160])
                    break

        # 2. One completion, kept verbatim. The point is to see whether the
        #    model's native template produced usable code, not to score it.
        single = _post("/chat/completions", {
            "model": model["short"],
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": GEN_TOKENS, "temperature": 0.0})
        text = single["choices"][0]["message"]["content"]
        row["sample"] = text
        row["has_code_block"] = "```" in text
        row["mentions_subprocess"] = "subprocess" in text
        print(f"  sample ({len(text)} chars), code block: {row['has_code_block']}")
        print("  " + text.strip().splitlines()[0][:100] if text.strip() else "  (empty)")

        # 3. Batched throughput. This number sets the budget for the real study,
        #    so it is measured concurrently rather than one request at a time.
        def one(i):
            return _post("/chat/completions", {
                "model": model["short"],
                "messages": [{"role": "user", "content": PROMPT}],
                "max_tokens": GEN_TOKENS, "temperature": 0.8, "seed": i})

        t1 = time.time()
        with ThreadPoolExecutor(max_workers=BATCH) as pool:
            outs = list(pool.map(one, range(BATCH)))
        elapsed = time.time() - t1
        completion_tokens = sum(o["usage"]["completion_tokens"] for o in outs)
        row["batch_secs"] = round(elapsed, 1)
        row["completion_tok_s"] = round(completion_tokens / elapsed)
        row["peak_gpu_mb"] = peak_gpu_mb()
        print(f"  {BATCH} completions in {elapsed:.1f}s "
              f"= {row['completion_tok_s']} completion tok/s")
        print(f"  peak GPU memory across cards: {row['peak_gpu_mb']} MiB")

    except Exception as exc:
        row["note"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAILED: {row['note']}"[:800])
    finally:
        stop_server(proc)
        free_weights(model)

    results.append(row)

print("\\nall models attempted")
'''

CELL_ANALYSERS = (Path(__file__).parent / "cells" / "analysers.py").read_text()

CELL_SUMMARY = (Path(__file__).parent / "cells" / "summary.py").read_text()

CELL_SHUTDOWN = '''\
# --- Emergency shutdown, if a cell was interrupted and the port is stuck. ---
subprocess.run("pkill -f vllm.entrypoints.openai.api_server", shell=True)
time.sleep(5)
print("port free:", _port_free())
'''

MD_AFTER = """\
## Reading the result

**All four load** -> the substrate is confirmed and the real study can be designed
against the measured throughput.

**One fails** -> substitute from the fallbacks, in preference order:
`mistralai/Mistral-7B-Instruct-v0.3` (Apache 2.0, ungated, but general rather than
code-specialised), `microsoft/Phi-3.5-mini-instruct` (3.8B, a size outlier), or
`meta-llama/Llama-3.1-8B-Instruct` (gated: needs license acceptance and an
`HF_TOKEN` secret).

**Several fail the same way** -> read `/kaggle/working/smoke-logs/*.log` before
changing anything. A shared failure is usually one environment problem, not four
model problems.

## What this deliberately does not do

It produces no research result and makes no claim. Its only job is to convert four
assumptions into four measurements before any GPU time is spent on the real run.
"""


def code(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.splitlines(keepends=True)}


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def build() -> dict:
    return {
        "cells": [
            md(MD_INTRO),
            md("## 1. Accelerator"), code(CELL_GPU),
            md("## 2. Install"), code(CELL_INSTALL),
            md("## 3. Configuration"), code(CELL_CONFIG),
            md("## 4. Server helpers"), code(CELL_SERVER),
            md("## 5. Measure each model"), code(CELL_RUN),
            md("## 6. Analysers"), code(CELL_ANALYSERS),
            md("## 7. Verdict"), code(CELL_SUMMARY),
            md("## 8. Emergency shutdown (only if needed)"), code(CELL_SHUTDOWN),
            md(MD_AFTER),
        ],
        "metadata": {
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 4,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
