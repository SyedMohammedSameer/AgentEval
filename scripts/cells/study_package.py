# --- The tested package. ---
# Cloned rather than pasted in. The notebook stays a driver, the code it runs is
# the same code the repository's tests cover, and the commit sha is printed and
# recorded in the manifest, so the run is pinned to something a reader can go and
# review rather than to a copy living inside this file.
REPO = "https://github.com/SyedMohammedSameer/AgentEval.git"
BRANCH = "claude/project-recall-m7l4nj"
SRC_ROOT = os.path.join(WORK_ROOT, "AgentEval")

if os.path.isdir(os.path.join(SRC_ROOT, ".git")):
    sh(f"git -C {SRC_ROOT} fetch --depth 1 origin {BRANCH}")
    sh(f"git -C {SRC_ROOT} reset --hard FETCH_HEAD")
else:
    sh(f"git clone --depth 1 --branch {BRANCH} {REPO} {SRC_ROOT}")

COMMIT = subprocess.run(f"git -C {SRC_ROOT} rev-parse HEAD", shell=True,
                        capture_output=True, text=True).stdout.strip()

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

import agentverif.report          # noqa: E402
import agentverif.study           # noqa: E402

print(f"\nagentverif @ {BRANCH} {COMMIT[:12]}")
print(f"read it at {REPO[:-4]}/tree/{COMMIT}/agentverif")
