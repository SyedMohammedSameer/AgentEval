# --- Pick the shown and held-out analysers from data, not from assumption. ---
# The corpus check turned up two problems. Semgrep's p/python pack fired on
# nothing across 25 BigCodeBench solutions, which would leave Bandit as the only
# held-out analyser and Bandit is a Ruff reimplementation. And findings are
# sparse, roughly 1.5 per task among tasks that have any, so the study has to
# reason per finding rather than per task.
#
# What the design needs is a pair of analysers that are:
#   * dense enough to give findings to fix,
#   * overlapping enough that a genuine fix is visible to both,
#   * independent enough that satisfying one does not trivially satisfy the other.
# This measures all three across a matrix of candidates.
import json
import os
import subprocess
import tempfile

SAMPLE = 80          # canonical solutions to analyse
PER_TOOL_TIMEOUT = 60


def _run(cmd, timeout=PER_TOOL_TIMEOUT):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def ruff(path, select):
    r = _run(f"ruff check --select {select} --output-format=json --isolated {path}")
    if r is None:
        return None
    try:
        return [(f["location"]["row"], f["code"]) for f in json.loads(r.stdout or "[]")]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def bandit(path):
    r = _run(f"bandit -q -f json {path}")
    if r is None:
        return None
    try:
        return [(f["line_number"], f["test_id"])
                for f in json.loads(r.stdout or "{}").get("results", [])]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def semgrep(path, config):
    r = _run(f"semgrep --config={config} --quiet --json --timeout=30 --metrics=off {path}")
    if r is None:
        return None
    try:
        return [(f["start"]["line"], f["check_id"].split(".")[-1])
                for f in json.loads(r.stdout or "{}").get("results", [])]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def pylint(path):
    r = _run(f"pylint --output-format=json --score=n --disable=C0114,C0115,C0116 {path}")
    if r is None:
        return None
    try:
        return [(f["line"], f["message-id"]) for f in json.loads(r.stdout or "[]")]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def mypy(path):
    r = _run(f"mypy --no-error-summary --ignore-missing-imports {path}")
    if r is None:
        return None
    out = []
    for line in (r.stdout or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1].strip().isdigit():
            out.append((int(parts[1]), "mypy"))
    return out


CANDIDATES = {
    "ruff[S]": lambda p: ruff(p, "S"),
    "ruff[S,B]": lambda p: ruff(p, "S,B"),
    "ruff[S,B,SIM,RET,ARG,PERF,C90]": lambda p: ruff(p, "S,B,SIM,RET,ARG,PERF,C90"),
    "bandit": bandit,
    "semgrep[p/python]": lambda p: semgrep(p, "p/python"),
    "semgrep[p/security-audit]": lambda p: semgrep(p, "p/security-audit"),
    "semgrep[p/default]": lambda p: semgrep(p, "p/default"),
    "pylint": pylint,
    "mypy": mypy,
}

targets = order[:SAMPLE]
print(f"analysing {len(targets)} canonical solutions with {len(CANDIDATES)} tools\n")

d = tempfile.mkdtemp()
paths = []
for n, i in enumerate(targets):
    rec = records[i]
    # Solution only: the test body is never shown to the agent and must not be
    # counted as part of the code under study.
    src = (rec.get("complete_prompt") or "") + (rec.get("canonical_solution") or "")
    path = os.path.join(d, f"t{n:03d}.py")
    with open(path, "w") as fh:
        fh.write(src)
    paths.append(path)

findings = {}
for name, fn in CANDIDATES.items():
    per_file, failed = [], 0
    for path in paths:
        res = fn(path)
        if res is None:
            failed += 1
            per_file.append([])
        else:
            per_file.append(res)
    findings[name] = per_file
    hits = sum(1 for f in per_file if f)
    total = sum(len(f) for f in per_file)
    status = f"  ({failed} could not run)" if failed else ""
    print(f"  {name:32s} {hits:3d}/{len(paths)} files ({hits / len(paths):4.0%})  "
          f"{total:4d} findings  {total / len(paths):4.1f}/file{status}")

# Overlap: of the findings one tool reports, what share does another report on the
# same line? High overlap means a genuine fix is visible to both, which is what
# makes the held-out tool a valid check rather than a different question.
print(f"\n{'shown':32s} {'held-out':32s} {'lines both see':>15s}")
usable = [n for n in CANDIDATES if sum(len(f) for f in findings[n]) >= 20]
for a in usable:
    for b in usable:
        if a == b:
            continue
        shared = matched = 0
        for fa, fb in zip(findings[a], findings[b]):
            lines_b = {ln for ln, _ in fb}
            for ln, _ in fa:
                shared += 1
                matched += ln in lines_b
        if shared:
            print(f"  {a:32s} {b:32s} {matched / shared:14.0%}")

print("\nWhat to look for: a shown analyser with enough density to give the agent")
print("something to fix, paired with a held-out one that sees the same lines but is")
print("built on a different engine. Bandit against ruff[S] is the suppression test;")
print("a second pairing with real overlap is what tests generalisation.")
