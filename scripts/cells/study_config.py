# ============================== CONFIGURATION ==============================
# Four families, four pretraining corpora, all code-specialised instruct models
# inside a 1.3x size spread, all Llama or Qwen2 architecture, all ungated.
MODELS = [
    {"hf": "Qwen/Qwen2.5-Coder-7B-Instruct",            "short": "qwen2.5-coder-7b",    "family": "Alibaba"},
    {"hf": "deepseek-ai/deepseek-coder-6.7b-instruct",  "short": "deepseek-coder-6.7b", "family": "DeepSeek"},
    {"hf": "01-ai/Yi-Coder-9B-Chat",                    "short": "yi-coder-9b",         "family": "01.AI"},
    {"hf": "ibm-granite/granite-8b-code-instruct-128k", "short": "granite-8b-code",     "family": "IBM"},
]

SEED = 0            # fixes the task shuffle; every model walks the same order

# --- sized to the accelerator measured in section 1 -------------------------
# One GPU big enough to hold a 9B model is served with tensor parallelism off,
# which removes collective communication from the run entirely. That is not a
# tuning preference: NCCL and peer-to-peer across two cards is where this study
# has actually failed, and a single A100 deletes the whole class.
BIG_GPU = N_GPUS == 1 and GPU_MEM_GB >= 35
TP = 1 if BIG_GPU else min(2, N_GPUS)

# 4096 rather than 8192. The longest prompt this study sends is a repair prompt:
# the file, up to 40 findings, and the instruction, which measures under 1600
# tokens, against 1024 generated. Halving the window doubles how many sequences
# fit in KV cache, and on a multi-head model like deepseek-coder that is the
# difference between a wide batch and a narrow one.
MAX_MODEL_LEN = 4096
GPU_MEM_FRACTION = 0.90
MAX_GEN_TOKENS = 1024     # a full corrected file, not a diff
TEMPERATURE = 0.0         # one deterministic sample; the variance budget goes
                          # into tasks, which is where the estimate needs it

# An A100 has the memory to keep a far wider batch resident than a T4 pair, and
# the CPU-side work is what limits the run there, so both numbers move together.
MAX_NUM_SEQS = 128 if BIG_GPU else 32
WORKERS = 32 if BIG_GPU else 16

# More tasks where the hardware allows it. The headline denominator is findings
# that have a held-out counterpart, which is roughly an eighth of tasks, so task
# count is the direct lever on how tight the interval gets.
N_TASKS = 300 if BIG_GPU else 200

# Time. Hard stops, not estimates. Sizing a run by predicted token counts has been
# wrong before; sizing it by wall clock cannot be. The task order is a fixed
# shuffle, so a model that stops early holds a uniform random sample rather than a
# biased prefix.
TOTAL_BUDGET_S = 2.5 * 3600      # whole sweep, model loading included
PER_MODEL_BUDGET_S = 30 * 60
MIN_USEFUL_BUDGET_S = 6 * 60     # below this, skip rather than half-load

# Colab clears /content when the runtime recycles. If Drive is already mounted,
# results go there so a disconnect costs no work. No mounting is attempted: that
# would block the run on an auth prompt.
DRIVE = "/content/drive/MyDrive"
OUT_DIR = (os.path.join(DRIVE, "agenteval-results") if os.path.isdir(DRIVE)
           else os.path.join(WORK_ROOT, "results"))
STEPS_PATH = os.path.join(OUT_DIR, "steps.jsonl")
LOG_DIR = os.path.join(WORK_ROOT, "study-logs")
for d in (OUT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)
# ===========================================================================

print(f"{len(MODELS)} models | tensor-parallel {TP} | {DTYPE} | "
      f"{MAX_NUM_SEQS} server slots | {WORKERS} workers | {N_TASKS} tasks each")
print(f"budget: {TOTAL_BUDGET_S / 3600:.1f}h total, "
      f"{PER_MODEL_BUDGET_S / 60:.0f} min per model")
print(f"results: {OUT_DIR}"
      + ("  (on Drive, survives a disconnect)" if DRIVE in OUT_DIR else ""))
if os.path.exists(STEPS_PATH):
    print("checkpoint exists - this run will resume rather than restart")
