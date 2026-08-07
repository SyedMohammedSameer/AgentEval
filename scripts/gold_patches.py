"""Known-good fixes for the original single-file tasks.

These exist purely so `validate_benchmark.py` can prove each task is solvable. They
are written to `benchmarks/local/<task>/solution/`, which is never copied into an
agent's environment — only `workspace/` is.

Kept separate from the task definitions so the fix sits next to nothing that
describes the bug, and so adding a gold patch to an existing task is a one-entry
change rather than an edit inside a long literal.

Keyed by task id; each value maps a workspace-relative filename to its fixed contents.
"""

from __future__ import annotations

GOLD_PATCHES: dict[str, dict[str, str]] = {
    "slugify-collapse-dashes": {
        "textutils.py": '''\
import re


def slugify(text: str) -> str:
    text = text.lower()
    # Collapse each *run* of non-alphanumeric characters to one hyphen, then trim
    # the hyphens a leading or trailing run leaves behind.
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")
''',
    },
    "dedup-preserve-order": {
        "seqtools.py": '''\
def dedup(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
''',
    },
    "roman-subtractive": {
        "roman.py": '''\
def to_roman(n: int) -> str:
    # Subtractive pairs sit between the additive symbols, so the greedy walk
    # consumes them before falling back to repetition.
    values = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    out = []
    for value, symbol in values:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)
''',
    },
    "running-median-window": {
        "stats.py": '''\
def moving_average(nums, k):
    out = []
    # There are len(nums) - k + 1 windows of width k, not len(nums) - k.
    for i in range(len(nums) - k + 1):
        window = nums[i:i + k]
        out.append(sum(window) / k)
    return out
''',
    },
    "balanced-brackets": {
        "brackets.py": '''\
def is_balanced(s: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack
''',
    },
    "graph-cycle-detect": {
        "graph.py": '''\
def has_cycle(adj):
    # Three-color DFS: grey marks nodes on the current recursion stack, so only a
    # back-edge counts as a cycle. A plain visited set also flags cross-edges,
    # which are legal in a DAG.
    WHITE, GREY, BLACK = 0, 1, 2
    color = {}

    def dfs(node):
        color[node] = GREY
        for nxt in adj.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GREY:
                return True
            if state == WHITE and dfs(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color.get(n, WHITE) == WHITE and dfs(n) for n in list(adj))
''',
    },
    "caesar-cipher-wrap": {
        "cipher.py": '''\
def encode(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            # Modulo keeps the shift inside the 26-letter alphabet, and handles
            # negative shifts as well.
            out.append(chr(base + (ord(ch) - base + shift) % 26))
        else:
            out.append(ch)
    return "".join(out)
''',
    },
    "flatten-deep": {
        "nest.py": '''\
def flatten(nested):
    out = []
    for item in nested:
        if isinstance(item, list):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out
''',
    },
    "merge-intervals": {
        "intervals.py": '''\
def merge(intervals):
    intervals = sorted(intervals)
    merged = []
    for start, end in intervals:
        # <= so intervals that merely touch, like [1,2] and [2,3], combine.
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''',
    },
    "rle-encode-last-run": {
        "rle.py": '''\
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
    # The loop only emits a run when it *changes*, so the final run needs
    # flushing after it ends.
    out.append(f"{prev}{count}")
    return "".join(out)
''',
    },
    "binary-search-bounds": {
        "bsearch.py": '''\
def search(arr, target):
    # hi is an inclusive bound, so it starts one past the last valid index only
    # if the loop condition were `<`. With `<=` it must be len(arr) - 1.
    lo, hi = 0, len(arr) - 1
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
    },
    "chunk-list": {
        "chunk.py": '''\
def chunk(lst, n):
    out = []
    # Step by n for consecutive chunks; stepping by 1 gives sliding windows.
    for i in range(0, len(lst), n):
        out.append(lst[i:i + n])
    return out
''',
    },
}
