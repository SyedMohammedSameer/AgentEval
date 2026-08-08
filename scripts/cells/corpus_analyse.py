# --- The number that sets the budget: how many tasks have anything to fix? ---
# The study can only measure whether a fix transfers on code that has findings in
# the first place. That share is the screening hit rate, and it decides how many
# tasks must be generated to reach the target of 150 analysable ones.
#
# Rule selection matters as much as the corpus. Ruff's S rules mirror Bandit,
# which makes them the sharp shown/held-out pair, but security findings alone may
# be rare in benign code. Broader selections find more and overlap less cleanly.
# Rather than guess, measure the hit rate under each and let the data choose.
RULE_SETS = {
    "S": "security only, mirrors Bandit most closely",
    "S,B": "security plus bugbear",
    "S,B,C90,PERF": "security, bugbear, complexity, performance",
}


def ruff_findings(path, select):
    r = subprocess.run(
        f"ruff check --select {select} --output-format=json --isolated {path}",
        shell=True, capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def bandit_findings(path):
    r = subprocess.run(f"bandit -q -f json {path}", shell=True,
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}").get("results", [])
    except json.JSONDecodeError:
        return []


def semgrep_findings(path):
    r = subprocess.run(f"semgrep --config=p/python --quiet --json --timeout=20 {path}",
                       shell=True, capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}").get("results", [])
    except json.JSONDecodeError:
        return None      # None means semgrep could not run, distinct from zero


# Analyse the *reference* solutions of the tasks that actually run. These are
# human-curated, so they are cleaner than model output will be: treat the rate
# below as a lower bound on the screening hit rate the study will see.
targets = [r["idx"] for r in exec_results if r["ok"]] or order[:SAMPLE_N]
print(f"analysing {len(targets)} reference solutions\n")

rows = []
d = tempfile.mkdtemp()
for n, i in enumerate(targets):
    rec = records[i]
    src = assemble(rec, best_strategy).split("\n\nclass Test")[0]   # drop the test body
    path = os.path.join(d, f"t{n}.py")
    with open(path, "w") as fh:
        fh.write(src)
    row = {"task_id": rec.get("task_id"), "loc": src.count("\n") + 1}
    for name, select in [(k, k) for k in RULE_SETS]:
        row[f"ruff[{name}]"] = len(ruff_findings(path, select))
    row["bandit"] = len(bandit_findings(path))
    sg = semgrep_findings(path) if n < 25 else None    # semgrep is slow; sample it
    row["semgrep"] = len(sg) if sg is not None else -1
    rows.append(row)

print(f"{'rule set':16s} {'tasks with >=1':>15s} {'hit rate':>9s} {'mean findings':>14s}")
hit_rates = {}
for name in RULE_SETS:
    key = f"ruff[{name}]"
    hits = sum(1 for r in rows if r[key] > 0)
    mean = sum(r[key] for r in rows) / len(rows)
    hit_rates[name] = hits / len(rows)
    print(f"{name:16s} {hits:>10d}/{len(rows):<4d} {hits / len(rows):>8.0%} {mean:>14.1f}")

b_hits = sum(1 for r in rows if r["bandit"] > 0)
print(f"{'bandit':16s} {b_hits:>10d}/{len(rows):<4d} {b_hits / len(rows):>8.0%} "
      f"{sum(r['bandit'] for r in rows) / len(rows):>14.1f}")

sg_rows = [r for r in rows if r["semgrep"] >= 0]
if sg_rows:
    s_hits = sum(1 for r in sg_rows if r["semgrep"] > 0)
    print(f"{'semgrep':16s} {s_hits:>10d}/{len(sg_rows):<4d} {s_hits / len(sg_rows):>8.0%} "
          f"{sum(r['semgrep'] for r in sg_rows) / len(sg_rows):>14.1f}")
else:
    print(f"{'semgrep':16s} could not run: the cross-engine held-out arm is unavailable")

print(f"\nmean file length: {sum(r['loc'] for r in rows) / len(rows):.0f} lines")
print("\nThese are curated reference solutions, so model output should trip the")
print("analysers at least this often. Treat these as lower bounds.")
