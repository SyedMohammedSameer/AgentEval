# --- Install, on whichever host this is. ~5-10 min, mostly vLLM's deps. ---
# vLLM is only ever launched as a subprocess, so this kernel never imports torch.
# That matters most on Colab, where torch is preloaded: installing vLLM changes
# torch on disk, and a kernel that had already imported the old one would need a
# restart. Nothing here does, so there is no restart and no lost state.
import os
import re
import shutil

# Set to pin explicitly, e.g. "vllm==0.10.2". Empty lets the CUDA check below
# choose, which is what it is for.
VLLM_SPEC = ""

if os.path.isdir("/kaggle/working"):
    PLATFORM, WORK_ROOT, SCRATCH = "kaggle", "/kaggle/working", "/kaggle/temp"
elif os.path.isdir("/content"):
    PLATFORM, WORK_ROOT, SCRATCH = "colab", "/content", "/content/scratch"
else:
    PLATFORM, WORK_ROOT, SCRATCH = "local", os.getcwd(), "/tmp"
os.makedirs(SCRATCH, exist_ok=True)


def sh(cmd, check=True):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {cmd}")
    return r.returncode


# --- vLLM, matched to the CUDA this driver actually supports -----------------
# `pip install -U vllm` fetches a wheel built against whatever CUDA the current
# release targets. When that is newer than the host's, the extension module fails
# to load with `libcudart.so.NN: cannot open shared object file` and every launch
# dies identically. Colab and Kaggle are both CUDA 12 images, so the newest wheel
# is not always the right one. Pick by the driver, then prove it imports.
_smi_text = subprocess.run("nvidia-smi", shell=True, capture_output=True,
                           text=True).stdout
_m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", _smi_text)
DRIVER_CUDA = (int(_m.group(1)), int(_m.group(2))) if _m else (0, 0)
print(f"platform: {PLATFORM} | driver supports CUDA {DRIVER_CUDA[0]}.{DRIVER_CUDA[1]}")

def available_vllm_versions():
    """Every vLLM release PyPI actually has, newest first.

    Asking beats guessing: a hardcoded `vllm==0.11.2` that was never published
    spends a whole install attempt discovering the version does not exist.
    """
    out = ""
    for cmd in (f"{sys.executable} -m pip index versions vllm",
                f"{sys.executable} -m pip install 'vllm==' "):
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if "," in out or "Available versions" in out:
            break
    seen, vers = set(), []
    for v in re.findall(r"\b(\d+\.\d+\.\d+(?:\.?post\d+)?)\b", out):
        if v not in seen and not v.startswith("0.0"):
            seen.add(v)
            vers.append(v)

    def key(v):
        return [int(p) for p in v.split(".post")[0].split(".")]

    return sorted(vers, key=key, reverse=True)


def newest_in(versions, series):
    """Highest published patch of a minor series, e.g. '0.11' -> '0.11.2'."""
    xs = [v for v in versions if v.startswith(series + ".")]
    return xs[0] if xs else None


AVAILABLE = available_vllm_versions()
print(f"vLLM releases on PyPI: {len(AVAILABLE)}"
      + (f", newest {AVAILABLE[0]}" if AVAILABLE else " (could not list)"))

if VLLM_SPEC:
    CANDIDATES = [VLLM_SPEC]
else:
    # Series that predate vLLM's move to CUDA 13, newest first, resolved to
    # whatever patch actually exists. On a CUDA 13 host the newest wheel is
    # correct and is tried first instead.
    older = [f"vllm=={v}" for v in
             (newest_in(AVAILABLE, s) for s in ("0.11", "0.10", "0.9")) if v]
    CANDIDATES = (["-U vllm"] + older if DRIVER_CUDA[0] >= 13
                  else older + ["-U vllm"])
    if not older:      # listing failed; fall back to fixed pins
        CANDIDATES = ["-U vllm", "vllm==0.10.2", "vllm==0.9.2"]
print("will try, in order:", CANDIDATES)

# The gate. `import vllm` in a subprocess is the cheapest possible proof that the
# wheel matches this machine, and it takes under a minute. Not doing this cost a
# whole session: four models times three launch configurations, all dying on the
# same missing library, none of which was a model problem at all.
_CHECK = ("import torch, vllm; "
          "assert torch.cuda.is_available(), 'torch cannot see the GPU'; "
          "print(vllm.__version__, torch.__version__, torch.version.cuda)")

VLLM_BUILD = ""
for spec in CANDIDATES:
    print(f"\n--- trying {spec} ---")
    sh(f"pip install -q {spec}", check=False)
    probe = subprocess.run([sys.executable, "-c", _CHECK], capture_output=True,
                           text=True, timeout=900)
    if probe.returncode == 0:
        VLLM_BUILD = probe.stdout.strip()
        print(f"OK: vllm/torch/cuda = {VLLM_BUILD}")
        break
    tail = (probe.stderr or "").strip().splitlines()
    print("  cannot import:", tail[-1][:200] if tail else "unknown error")

if not VLLM_BUILD:
    raise SystemExit(
        "No vLLM build on this list imports on this machine. The last error is "
        "printed above.\n\nIf it names a missing libcudart, the wheel was built "
        "for a newer CUDA than this driver supports: set VLLM_SPEC at the top of "
        "this cell to an older release and re-run this cell only."
    )

# The analysers whose findings are the measurement.
sh("pip install -q ruff bandit pylint")

# BigCodeBench is library-heavy: its tests import Faker, textblob, wordcloud and
# friends, and a missing one fails the test no matter what the model wrote. No -U,
# and check=False, because one unavailable wheel must not end the run - the corpus
# cell measures what is actually importable and drops the rest.
sh("pip install -q Faker textblob wordcloud prettytable texttable natsort "
   "holidays xmltodict python-docx pyquery python-Levenshtein soundfile "
   "librosa docxtpl openpyxl xlrd", check=False)

# datasets ships on both hosts. Installing it with -U after vLLM can pull a newer
# numpy or pyarrow underneath vLLM's compiled extensions and break the engine at
# load time, so it is only installed if genuinely missing, and never upgraded.
try:
    import datasets  # noqa: F401
except ImportError:
    sh("pip install -q datasets")

# Versions are part of the result: findings depend on analyser versions, and
# whether the engine starts at all depends on vLLM, torch and CUDA.
TOOL_VERSIONS = {"platform": PLATFORM, "gpu": f"{N_GPUS}x{GPU_MEM_GB:.0f}GB",
                 "dtype": DTYPE, "driver_cuda": f"{DRIVER_CUDA[0]}.{DRIVER_CUDA[1]}",
                 "vllm_torch_cuda": VLLM_BUILD}
for tool in ("ruff", "bandit", "pylint"):
    r = subprocess.run(f"{tool} --version", shell=True, capture_output=True, text=True)
    out = (r.stdout or r.stderr or "?").strip().splitlines()
    TOOL_VERSIONS[tool] = out[0] if out else "?"
for pkg in ("vllm", "torch", "numpy", "transformers", "datasets"):
    r = subprocess.run(f"pip show {pkg} 2>/dev/null | grep -i '^Version:'",
                       shell=True, capture_output=True, text=True)
    TOOL_VERSIONS[pkg] = r.stdout.strip().split(":", 1)[-1].strip() or "?"
TOOL_VERSIONS["python"] = sys.version.split()[0]
print()
for k, v in TOOL_VERSIONS.items():
    print(f"  {k:16s} {v}")

# Weights go to scratch, never to the saved-output directory, which is size-capped
# on Kaggle and synced on Colab if Drive is mounted.
HF_CACHE = os.path.join(SCRATCH, "hf")
os.makedirs(HF_CACHE, exist_ok=True)
os.environ["HF_HOME"] = HF_CACHE
free_gb = shutil.disk_usage(SCRATCH).free / 1e9
print(f"\nHF cache: {HF_CACHE}  ({free_gb:.0f} GB free)")
if free_gb < 25:
    print("WARNING: under 25 GB free. Weights are freed after each model, but a "
          "single model needs ~18 GB.")
