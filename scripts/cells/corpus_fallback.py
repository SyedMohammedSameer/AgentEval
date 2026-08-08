# --- Fallback: EvalPlus. Run this ONLY if the verdict cell said STOP. ---
# EvalPlus (HumanEval+ / MBPP+) is trivial to run: pure-Python tasks, no exotic
# dependencies, so the runnable share should be near total.
#
# The cost is construct validity. Its tasks are short standalone functions, which
# give a static analyser very little to find, so the study would be measuring
# transfer on a handful of findings per file rather than on realistic code. That
# is a genuine weakening of the result and belongs in the limitations section, not
# hidden in a config.
for cid in ("evalplus/humanevalplus", "evalplus/mbppplus"):
    try:
        alt = load_dataset(cid)
        split = list(alt.keys())[0]
        recs = alt[split]
        print(f"{cid}: {len(recs)} tasks, fields {list(recs[0].keys())}")

        d = tempfile.mkdtemp()
        hits = 0
        n = min(40, len(recs))
        for i in range(n):
            body = (recs[i].get("canonical_solution") or recs[i].get("solution") or "")
            head = recs[i].get("prompt") or ""
            path = os.path.join(d, f"f{i}.py")
            with open(path, "w") as fh:
                fh.write(head + body)
            if len(ruff_findings(path, "S,B,C90,PERF")) > 0:
                hits += 1
        print(f"  {hits}/{n} carry a finding at the broad rule set ({hits / n:.0%})")
        print(f"  mean length {sum((recs[i].get('prompt') or '').count(chr(10)) for i in range(n)) / n:.0f} lines")
    except Exception as exc:
        print(f"{cid}: {type(exc).__name__}: {str(exc)[:140]}")

print("\nIf the hit rate here is also low, the problem is the rule selection rather")
print("than the corpus, and the fix is to widen it rather than to change dataset.")
