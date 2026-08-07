"""Author the synthetic local benchmark.

Each task is a small, self-contained Python module with a genuine bug, a *visible*
basic test file the agent can run (via the run_tests tool), and a *hidden* oracle
test file used only for scoring. This mirrors real development: you have some tests,
CI has more. Run:  python scripts/build_local_benchmark.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gold_patches import GOLD_PATCHES
from tasks_advanced import ADVANCED_TASKS
from tasks_extended import EXTENDED_TASKS

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "local"


TASKS: list[dict] = [
    # ------------------------------------------------------------------ slugify
    {
        "id": "slugify-collapse-dashes",
        "module": "textutils.py",
        "problem": (
            "`slugify(text)` in textutils.py converts a string to a URL slug. It currently "
            "leaves runs of multiple spaces/punctuation as repeated hyphens and can produce "
            "leading/trailing hyphens. Fix it so that: consecutive non-alphanumeric characters "
            "collapse to a single hyphen, and there are no leading or trailing hyphens. "
            "Output must be lowercase."
        ),
        "buggy": '''\
import re


def slugify(text: str) -> str:
    text = text.lower()
    # BUG: replaces each non-alphanumeric char with its own hyphen, and does not
    # strip leading/trailing hyphens.
    return re.sub(r"[^a-z0-9]", "-", text)
''',
        "basic": '''\
from textutils import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"


def test_trailing_punct():
    assert slugify("Hello!!!") == "hello"
''',
        "oracle": '''\
from textutils import slugify


def test_multiple_spaces():
    assert slugify("a   b") == "a-b"


def test_leading_trailing():
    assert slugify("  Hello World  ") == "hello-world"


def test_mixed_punct():
    assert slugify("Foo -- Bar/Baz") == "foo-bar-baz"


def test_numbers_kept():
    assert slugify("Route 66!") == "route-66"
''',
    },
    # -------------------------------------------------------------- dedup order
    {
        "id": "dedup-preserve-order",
        "module": "seqtools.py",
        "problem": (
            "`dedup(items)` in seqtools.py should remove duplicates while preserving the order "
            "of first appearance. It currently returns items in an arbitrary order because it "
            "goes through a set. Fix it to preserve first-seen order."
        ),
        "buggy": '''\
def dedup(items):
    # BUG: set() destroys ordering.
    return list(set(items))
''',
        "basic": '''\
from seqtools import dedup


def test_basic():
    assert dedup([1, 1, 2, 3]) == [1, 2, 3]


def test_order_of_first_appearance():
    assert dedup([3, 1, 3, 2]) == [3, 1, 2]
''',
        "oracle": '''\
from seqtools import dedup


def test_order_preserved():
    assert dedup([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_strings():
    assert dedup(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


def test_empty():
    assert dedup([]) == []
''',
    },
    # ------------------------------------------------------------ roman numeral
    {
        "id": "roman-subtractive",
        "module": "roman.py",
        "problem": (
            "`to_roman(n)` in roman.py converts an integer (1..3999) to a Roman numeral, but it "
            "does not handle subtractive notation (4, 9, 40, 90, 400, 900), so it returns e.g. "
            "'IIII' instead of 'IV'. Fix it to use standard subtractive notation."
        ),
        "buggy": '''\
def to_roman(n: int) -> str:
    # BUG: no subtractive pairs, so 4 -> "IIII", 9 -> "VIIII", etc.
    values = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]
    out = []
    for value, symbol in values:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)
''',
        "basic": '''\
from roman import to_roman


def test_simple():
    assert to_roman(3) == "III"


def test_four():
    assert to_roman(4) == "IV"
''',
        "oracle": '''\
from roman import to_roman


def test_nine():
    assert to_roman(9) == "IX"


def test_forty():
    assert to_roman(40) == "XL"


def test_composite():
    assert to_roman(1994) == "MCMXCIV"


def test_year():
    assert to_roman(2023) == "MMXXIII"
''',
    },
    # ------------------------------------------------------------- running mean
    {
        "id": "running-median-window",
        "module": "stats.py",
        "problem": (
            "`moving_average(nums, k)` in stats.py should return the list of averages of every "
            "contiguous window of size k. It currently has an off-by-one error in the range and "
            "raises IndexError / drops the last window. Fix the windowing."
        ),
        "buggy": '''\
def moving_average(nums, k):
    out = []
    # BUG: range end should be len(nums) - k + 1, so the last window is dropped.
    for i in range(len(nums) - k):
        window = nums[i:i + k]
        out.append(sum(window) / k)
    return out
''',
        "basic": '''\
from stats import moving_average


def test_basic():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]
''',
        "oracle": '''\
from stats import moving_average


def test_window_three():
    assert moving_average([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]


def test_full_window():
    assert moving_average([2, 4, 6], 3) == [4.0]


def test_k_one():
    assert moving_average([5, 6, 7], 1) == [5.0, 6.0, 7.0]
''',
    },
    # ----------------------------------------------------------- bracket match
    {
        "id": "balanced-brackets",
        "module": "brackets.py",
        "problem": (
            "`is_balanced(s)` in brackets.py checks whether brackets ()[]{} are balanced and "
            "properly nested. It currently only counts opens vs closes and ignores nesting/type, "
            "so '([)]' and '(]' are wrongly reported as balanced. Fix it to check proper nesting."
        ),
        "buggy": '''\
def is_balanced(s: str) -> bool:
    # BUG: only counts totals, ignores order and bracket type.
    opens = sum(s.count(c) for c in "([{")
    closes = sum(s.count(c) for c in ")]}")
    return opens == closes
''',
        "basic": '''\
from brackets import is_balanced


def test_ok():
    assert is_balanced("()[]{}") is True


def test_bad_count():
    assert is_balanced("(()") is False


def test_mismatched_types():
    assert is_balanced("(]") is False
''',
        "oracle": '''\
from brackets import is_balanced


def test_wrong_order():
    assert is_balanced("([)]") is False


def test_wrong_type():
    assert is_balanced("(]") is False


def test_nested_ok():
    assert is_balanced("{[()()]}") is True


def test_empty():
    assert is_balanced("") is True
''',
    },
    # -------------------------------------------------------------- cycle check
    {
        "id": "graph-cycle-detect",
        "module": "graph.py",
        "problem": (
            "`has_cycle(adj)` in graph.py detects whether a directed graph (adjacency dict) has "
            "a cycle. It uses a single visited set and so misreports DAGs with shared descendants "
            "as cyclic, and can miss real cycles. Implement correct DFS cycle detection using a "
            "recursion/on-stack set."
        ),
        "buggy": '''\
def has_cycle(adj):
    visited = set()

    def dfs(node):
        # BUG: a plain visited set flags any re-encountered node as a cycle,
        # which is wrong for DAGs with shared descendants.
        if node in visited:
            return True
        visited.add(node)
        for nxt in adj.get(node, []):
            if dfs(nxt):
                return True
        return False

    return any(dfs(n) for n in list(adj))
''',
        "basic": '''\
from graph import has_cycle


def test_simple_cycle():
    assert has_cycle({"a": ["b"], "b": ["a"]}) is True


def test_no_cycle():
    assert has_cycle({"a": ["b"], "b": []}) is False
''',
        "oracle": '''\
from graph import has_cycle


def test_dag_shared_descendant():
    # a->b, a->c, b->d, c->d : NOT a cycle despite d seen twice.
    assert has_cycle({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}) is False


def test_self_loop():
    assert has_cycle({"a": ["a"]}) is True


def test_long_cycle():
    assert has_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) is True


def test_tree():
    assert has_cycle({"r": ["x", "y"], "x": [], "y": ["z"], "z": []}) is False
''',
    },
]


TASKS += [
    # ------------------------------------------------------------- caesar wrap
    {
        "id": "caesar-cipher-wrap",
        "module": "cipher.py",
        "problem": (
            "`encode(text, shift)` in cipher.py is a Caesar cipher. It shifts letters but does "
            "not wrap around the alphabet, so shifting 'z' by 1 produces a non-letter instead of "
            "'a'. Non-letters must pass through unchanged, case must be preserved, and shifts "
            "larger than 26 must wrap. Fix the wrap-around."
        ),
        "buggy": '''\
def encode(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            # BUG: no modulo, so shifting past 'z' escapes the alphabet.
            out.append(chr(base + (ord(ch) - base) + shift))
        else:
            out.append(ch)
    return "".join(out)
''',
        "basic": '''\
from cipher import encode


def test_simple():
    assert encode("abc", 1) == "bcd"


def test_wraps_past_z():
    assert encode("z", 1) == "a"
''',
        "oracle": '''\
from cipher import encode


def test_wrap_lower():
    assert encode("xyz", 3) == "abc"


def test_wrap_upper():
    assert encode("XYZ", 3) == "ABC"


def test_shift_over_26():
    assert encode("abc", 27) == "bcd"


def test_punct_passthrough():
    assert encode("a-b", 1) == "b-c"
''',
    },
    # ------------------------------------------------------------ deep flatten
    {
        "id": "flatten-deep",
        "module": "nest.py",
        "problem": (
            "`flatten(nested)` in nest.py should recursively flatten arbitrarily nested lists "
            "into a single flat list. It currently only flattens one level deep. Fix it to "
            "recurse to any depth."
        ),
        "buggy": '''\
def flatten(nested):
    out = []
    for item in nested:
        if isinstance(item, list):
            # BUG: only one level — nested sublists stay nested.
            out.extend(item)
        else:
            out.append(item)
    return out
''',
        "basic": '''\
from nest import flatten


def test_one_level():
    assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]


def test_two_levels():
    assert flatten([1, [2, [3, 4]]]) == [1, 2, 3, 4]
''',
        "oracle": '''\
from nest import flatten


def test_deep():
    assert flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4]


def test_lists_of_lists():
    assert flatten([[1], [2], [3]]) == [1, 2, 3]


def test_empty():
    assert flatten([]) == []
''',
    },
    # ---------------------------------------------------------- merge intervals
    {
        "id": "merge-intervals",
        "module": "intervals.py",
        "problem": (
            "`merge(intervals)` in intervals.py merges overlapping intervals (lists of "
            "[start, end]). It fails to merge intervals that merely touch, e.g. [1,2] and "
            "[2,3], because it uses a strict `<` comparison. Touching intervals should merge. "
            "Return merged intervals sorted by start."
        ),
        "buggy": '''\
def merge(intervals):
    intervals = sorted(intervals)
    merged = []
    for start, end in intervals:
        # BUG: strict `<` fails to merge touching intervals like [1,2],[2,3].
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''',
        "basic": '''\
from intervals import merge


def test_overlap():
    assert merge([[1, 3], [2, 6]]) == [[1, 6]]


def test_touching_intervals_merge():
    assert merge([[1, 2], [2, 3]]) == [[1, 3]]
''',
        "oracle": '''\
from intervals import merge


def test_touching():
    assert merge([[1, 2], [2, 3]]) == [[1, 3]]


def test_disjoint():
    assert merge([[1, 4], [5, 6]]) == [[1, 4], [5, 6]]


def test_nested():
    assert merge([[1, 4], [2, 3]]) == [[1, 4]]
''',
    },
    # -------------------------------------------------------------- rle encode
    {
        "id": "rle-encode-last-run",
        "module": "rle.py",
        "problem": (
            "`encode(s)` in rle.py does run-length encoding: 'aaabb' -> 'a3b2'. It drops the "
            "FINAL run because it only emits a run when the character changes. Fix it to emit "
            "the last run too. Empty input returns ''."
        ),
        "buggy": '''\
def encode(s: str) -> str:
    if not s:
        return ""
    out = []
    prev, count = s[0], 1
    for ch in s[1:]:
        if ch == prev:
            count += 1
        else:
            out.append(f"{prev}{count}")
            prev, count = ch, 1
    # BUG: the final run (prev/count) is never appended.
    return "".join(out)
''',
        "basic": '''\
from rle import encode


def test_basic():
    assert encode("aaab") == "a3b1"
''',
        "oracle": '''\
from rle import encode


def test_multi():
    assert encode("aaabbc") == "a3b2c1"


def test_single():
    assert encode("a") == "a1"


def test_empty():
    assert encode("") == ""
''',
    },
    # ----------------------------------------------------------- binary search
    {
        "id": "binary-search-bounds",
        "module": "bsearch.py",
        "problem": (
            "`search(arr, target)` in bsearch.py does binary search on a sorted list and returns "
            "the index or -1. The high bound is initialised to len(arr) instead of len(arr)-1, "
            "which causes an IndexError when the target is larger than all elements. Fix the "
            "bounds."
        ),
        "buggy": '''\
def search(arr, target):
    lo, hi = 0, len(arr)  # BUG: hi should be len(arr) - 1 for inclusive bounds.
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
''',
        "basic": '''\
from bsearch import search


def test_found():
    assert search([1, 2, 3], 2) == 1


def test_missing_high():
    assert search([1, 2, 3], 9) == -1
''',
        "oracle": '''\
from bsearch import search


def test_empty():
    assert search([], 1) == -1


def test_first():
    assert search([1, 2, 3, 4, 5], 1) == 0


def test_last():
    assert search([1, 2, 3, 4, 5], 5) == 4


def test_absent_middle():
    assert search([1, 3, 5, 7], 4) == -1
''',
    },
    # -------------------------------------------------------------- chunk list
    {
        "id": "chunk-list",
        "module": "chunk.py",
        "problem": (
            "`chunk(lst, n)` in chunk.py should split a list into consecutive chunks of size n "
            "(the last may be shorter). It currently steps by 1 instead of n, producing "
            "overlapping windows. Fix the step."
        ),
        "buggy": '''\
def chunk(lst, n):
    out = []
    # BUG: step of 1 yields overlapping windows instead of consecutive chunks.
    for i in range(0, len(lst)):
        out.append(lst[i:i + n])
    return out
''',
        "basic": '''\
from chunk import chunk


def test_even():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
''',
        "oracle": '''\
from chunk import chunk


def test_remainder():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_exact():
    assert chunk([1, 2, 3], 3) == [[1, 2, 3]]


def test_bigger_than_list():
    assert chunk([1, 2], 5) == [[1, 2]]
''',
    },
]


def task_files(t: dict) -> dict[str, str]:
    """Workspace sources for a task, normalizing the two authoring shapes.

    Single-file tasks declare `module`/`buggy`; multi-file tasks declare a `files`
    mapping. Everything downstream sees the same dict.
    """
    if "files" in t:
        return dict(t["files"])
    return {t["module"]: t["buggy"]}


def write_task(t: dict) -> None:
    d = ROOT / t["id"]
    if d.exists():
        shutil.rmtree(d)
    (d / "workspace").mkdir(parents=True)
    (d / "tests").mkdir(parents=True)

    for rel, content in task_files(t).items():
        path = d / "workspace" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    (d / "workspace" / "test_basic.py").write_text(t["basic"])
    (d / "tests" / "test_oracle.py").write_text(t["oracle"])

    # The gold patch is stored outside workspace/ so it is never copied into an
    # environment the agent can see. validate_benchmark.py is its only consumer.
    if t.get("fix"):
        for rel, content in t["fix"].items():
            path = d / "solution" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    yaml_text = (
        f"id: {t['id']}\n"
        f"problem_statement: |\n"
        + "".join(f"  {line}\n" for line in t["problem"].split("\n"))
        + "dev_test_cmd: python -m pytest -q test_basic.py\n"
        "eval_test_cmd: python -m pytest -q\n"
        "timeout: 120\n"
        f"multi_file: {str(len(task_files(t)) > 1).lower()}\n"
        f"has_gold_patch: {str(bool(t.get('fix'))).lower()}\n"
    )
    (d / "task.yaml").write_text(yaml_text)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    all_tasks = TASKS + ADVANCED_TASKS + EXTENDED_TASKS

    ids = [t["id"] for t in all_tasks]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise SystemExit(f"duplicate task ids: {sorted(duplicates)}")

    for t in all_tasks:
        # Single-file tasks keep their gold patch in gold_patches.py rather than
        # inline, so the fix never sits beside the text describing the bug.
        if "fix" not in t and t["id"] in GOLD_PATCHES:
            t = {**t, "fix": GOLD_PATCHES[t["id"]]}
        write_task(t)

    multi = sum(1 for t in all_tasks if len(task_files(t)) > 1)
    gold = sum(1 for t in all_tasks if t.get("fix"))
    print(f"Wrote {len(all_tasks)} tasks to {ROOT}")
    print(f"  {multi} multi-file, {gold} with gold patches")


if __name__ == "__main__":
    main()
