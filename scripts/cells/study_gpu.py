# --- Accelerator: measure it, then let every later cell size itself to it. ---
# This notebook runs on a single A100, a pair of T4s, or anything between, and
# nothing below is hardcoded for one of them. The three facts that change are how
# many GPUs there are, whether bfloat16 exists, and how much memory is free.
import subprocess, sys


def _smi(fields):
    r = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


raw = _smi("name,memory.total,compute_cap") or _smi("name,memory.total")
if not raw:
    raise SystemExit("No GPU. Colab: Runtime > Change runtime type > A100. "
                     "Kaggle: Accelerator > GPU T4 x2.")

gpus = [line.split(", ") for line in raw.splitlines()]
for g in gpus:
    print("  " + " | ".join(g))

names = " ".join(g[0] for g in gpus).lower()
caps = [float(g[2]) for g in gpus if len(g) > 2]
if "p100" in names or (caps and min(caps) < 7.0):
    raise SystemExit(
        "\nThis accelerator cannot run vLLM: it needs compute capability >= 7.0 "
        "and the P100 is 6.0. Pick an A100, an L4, or T4 x2."
    )

N_GPUS = len(gpus)
GPU_MEM_GB = min(int(g[1].split()[0]) for g in gpus) / 1024
# Turing has no bfloat16 and asking for it is a hard failure; Ampere and later
# prefer it, and it is the dtype these models were trained in.
DTYPE = "bfloat16" if caps and min(caps) >= 8.0 else "float16"

print(f"\n{N_GPUS} GPU(s), {GPU_MEM_GB:.0f} GB each, compute {caps or 'unknown'}"
      f"\ndtype: {DTYPE}")
if N_GPUS == 1 and GPU_MEM_GB >= 35:
    print("Single large GPU: tensor parallelism is off, which removes the "
          "collective-communication failures entirely.")
