# --- Install. ~5-10 min, mostly vLLM's dependencies. ---
# vLLM is only ever launched as a subprocess, so this kernel never imports torch
# and no kernel restart is needed.
import os

# Set this once a working version is known, e.g. "vllm==0.10.2". Empty means
# latest. The smoke test that confirmed all four models load on 2x T4 did not
# record which vLLM it used, which is exactly why the version is recorded below
# and pinnable here: sm75 is old enough that a release can drop it without notice.
VLLM_SPEC = ""


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
# friends, and a missing one fails the test no matter what the model wrote. Most
# already ship in the Kaggle image. No -U, and check=False, because a single
# unavailable wheel must not end the run - the corpus cell measures what is
# actually importable and drops the rest.
sh("pip install -q Faker textblob wordcloud prettytable texttable natsort "
   "holidays xmltodict python-docx pyquery python-Levenshtein soundfile "
   "librosa docxtpl openpyxl xlrd", check=False)

# datasets ships in the Kaggle image. Installing it with -U after vLLM can pull a
# newer numpy or pyarrow underneath vLLM's compiled extensions and break the
# engine at load time, so it is only installed if genuinely missing, and never
# upgraded.
try:
    import datasets  # noqa: F401
except ImportError:
    sh("pip install -q datasets")

# Versions are part of the result: findings depend on analyser versions, and
# whether the engine starts at all depends on the vLLM and torch versions. Not
# recording them last time is why this run had to be diagnosed by hand.
TOOL_VERSIONS = {}
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

# Weights must not land in /kaggle/working: that is the saved output and is
# size-capped. Scratch instead.
HF_CACHE = "/kaggle/temp/hf" if os.path.isdir("/kaggle/temp") else "/tmp/hf"
os.makedirs(HF_CACHE, exist_ok=True)
os.environ["HF_HOME"] = HF_CACHE
print("\nHF cache:", HF_CACHE)
