# --- Install, on whichever host this is. ~5-10 min, mostly vLLM's deps. ---
# vLLM is only ever launched as a subprocess, so this kernel never imports torch.
# That matters most on Colab, where torch is preloaded: installing vLLM changes
# torch on disk, and a kernel that had already imported the old one would need a
# restart. Nothing here does, so there is no restart and no lost state.
import os
import shutil

# Set once a working version is known, e.g. "vllm==0.10.2". Empty means latest.
VLLM_SPEC = ""

if os.path.isdir("/kaggle/working"):
    PLATFORM, WORK_ROOT, SCRATCH = "kaggle", "/kaggle/working", "/kaggle/temp"
elif os.path.isdir("/content"):
    PLATFORM, WORK_ROOT, SCRATCH = "colab", "/content", "/content/scratch"
else:
    PLATFORM, WORK_ROOT, SCRATCH = "local", os.getcwd(), "/tmp"
os.makedirs(SCRATCH, exist_ok=True)
print(f"platform: {PLATFORM}, working under {WORK_ROOT}")


def sh(cmd, check=True):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {cmd}")
    return r.returncode


sh(f"pip install -q {VLLM_SPEC or '-U vllm'}")

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
# whether the engine starts at all depends on vLLM and torch.
TOOL_VERSIONS = {"platform": PLATFORM, "gpu": f"{N_GPUS}x{GPU_MEM_GB:.0f}GB",
                 "dtype": DTYPE}
for tool in ("ruff", "bandit", "pylint"):
    r = subprocess.run(f"{tool} --version", shell=True, capture_output=True, text=True)
    out = (r.stdout or r.stderr or "?").strip().splitlines()
    TOOL_VERSIONS[tool] = out[0] if out else "?"
for pkg in ("vllm", "torch", "numpy", "transformers", "datasets"):
    r = subprocess.run(f"pip show {pkg} 2>/dev/null | grep -i '^Version:'",
                       shell=True, capture_output=True, text=True)
    TOOL_VERSIONS[pkg] = r.stdout.strip().split(":", 1)[-1].strip() or "?"
TOOL_VERSIONS["python"] = sys.version.split()[0]
for k, v in TOOL_VERSIONS.items():
    print(f"  {k:14s} {v}")

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
