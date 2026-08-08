# ============================== CONFIGURATION ==============================
# Four families, four pretraining corpora, all code-specialised instruct models
# inside a 1.3x size spread, all Llama or Qwen2 architecture, all ungated. Each
# is served at float16 across both T4s, so no quantisation kernel is involved on
# sm75 - the single largest unknown on this hardware, removed rather than managed.
MODELS = [
    {"hf": "Qwen/Qwen2.5-Coder-7B-Instruct",            "short": "qwen2.5-coder-7b",    "family": "Alibaba"},
    {"hf": "deepseek-ai/deepseek-coder-6.7b-instruct",  "short": "deepseek-coder-6.7b", "family": "DeepSeek"},
    {"hf": "01-ai/Yi-Coder-9B-Chat",                    "short": "yi-coder-9b",         "family": "01.AI"},
    {"hf": "ibm-granite/granite-8b-code-instruct-128k", "short": "granite-8b-code",     "family": "IBM"},
]

SEED = 0            # fixes the task shuffle; every model walks the same order
N_TASKS = 200       # ~25 measurable transfers per model, ~100 pooled

# Serving.
TP = min(2, N_GPUS)
MAX_MODEL_LEN = 8192
GPU_MEM_FRACTION = 0.90
MAX_NUM_SEQS = 64
MAX_GEN_TOKENS = 1024     # a full corrected file, not a diff
TEMPERATURE = 0.0         # one deterministic sample; the variance budget goes
                          # into tasks, which is where the estimate needs it

# Concurrency. Each worker alternates between waiting on the server and running
# analysers and tests as subprocesses, so workers well above the core count keep
# the GPU batch full without the CPU work ever blocking a generation.
WORKERS = 32

# Time. Both are hard stops, not estimates. Sizing a run by predicted token
# counts has been wrong before; sizing it by wall clock cannot be. The task order
# is a fixed shuffle, so a model that stops early holds a uniform random sample
# rather than a biased prefix.
TOTAL_BUDGET_S = 3.0 * 3600      # whole sweep, model loading included
PER_MODEL_BUDGET_S = 40 * 60
MIN_USEFUL_BUDGET_S = 6 * 60     # below this, skip rather than half-load

OUT_DIR = "/kaggle/working/results"
STEPS_PATH = os.path.join(OUT_DIR, "steps.jsonl")
LOG_DIR = "/kaggle/working/study-logs"
for d in (OUT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)
# ===========================================================================

print(f"{len(MODELS)} models, tensor-parallel {TP}, {WORKERS} workers, "
      f"{N_TASKS} tasks each")
print(f"budget: {TOTAL_BUDGET_S / 3600:.1f}h total, "
      f"{PER_MODEL_BUDGET_S / 60:.0f} min per model")
print(f"checkpoint: {STEPS_PATH}"
      f"{'  (exists - this run will resume)' if os.path.exists(STEPS_PATH) else ''}")
