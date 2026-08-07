"""Ten further multi-file tasks, taking the benchmark from 28 to 38.

Sizing rationale: 28 tasks give ~94% power to detect a large effect (a third of
tasks flipping) but only ~50% for a moderate one (a fifth). The context-construction
levers — repo map, history window — are plausibly moderate-sized, so at 28 tasks a
null there would be uninformative: indistinguishable from "we could not see it."
`agenteval power --effect 0.2` puts the 80%-power point at ~38 tasks, which is what
this file exists to reach.

Same schema and same constraints as `tasks_advanced.py`: a small package rather than
one module, a bug that only shows at the seam between files, domain logic with no
canonical published solution to recall, a visible test that fails on the buggy code,
and a gold patch stored outside `workspace/` so validation can prove solvability.
"""

from __future__ import annotations

EXTENDED_TASKS: list[dict] = [
    # ------------------------------------------------------------ state machine
    {
        "id": "fsm-guard-before-transition",
        "problem": (
            "`fsm.machine.Machine` drives a state machine whose transitions may carry a "
            "guard predicate. Two defects: the target state is applied *before* the guard is "
            "consulted, so a transition the guard rejects still moves the machine and still "
            "appends to history; and an event with no matching transition is silently ignored "
            "instead of raising `UnknownTransition`, which makes a typo look like a successful "
            "no-op. Fix both. `fire` returns True only when the machine actually moved."
        ),
        "files": {
            "fsm/__init__.py": "",
            "fsm/transitions.py": '''\
from dataclasses import dataclass
from typing import Callable


class UnknownTransition(Exception):
    """No transition matches this event from the current state."""


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str
    guard: Callable | None = None   # ctx -> bool; the move only happens if True
''',
            "fsm/machine.py": '''\
from fsm.transitions import Transition, UnknownTransition


class Machine:
    def __init__(self, initial: str, transitions):
        self.state = initial
        self.transitions = list(transitions)
        self.history = [initial]

    def _find(self, event: str):
        for t in self.transitions:
            if t.source == self.state and t.event == event:
                return t
        return None

    def fire(self, event: str, ctx: dict | None = None) -> bool:
        """Apply `event`; returns True if the machine moved."""
        t = self._find(event)
        if t is None:
            # BUG: an unmatched event is swallowed instead of raising
            # UnknownTransition, so a misspelled event looks like a no-op.
            return False
        # BUG: the move is applied before the guard is consulted, so a rejected
        # transition still changes state and is still recorded in history.
        self.state = t.target
        self.history.append(t.target)
        return t.guard is None or t.guard(ctx or {})
''',
        },
        "basic": '''\
from fsm.machine import Machine
from fsm.transitions import Transition


def _machine():
    return Machine("draft", [
        Transition("draft", "submit", "review"),
        Transition("review", "approve", "published",
                   guard=lambda c: c.get("is_admin", False)),
    ])


def test_simple_transition():
    m = _machine()
    assert m.fire("submit") is True
    assert m.state == "review"


def test_rejected_guard_does_not_move_state():
    m = _machine()
    m.fire("submit")
    assert m.fire("approve", {"is_admin": False}) is False
    assert m.state == "review"
''',
        "oracle": '''\
import pytest

from fsm.machine import Machine
from fsm.transitions import Transition, UnknownTransition


def _machine():
    return Machine("draft", [
        Transition("draft", "submit", "review"),
        Transition("review", "approve", "published",
                   guard=lambda c: c.get("is_admin", False)),
        Transition("review", "reject", "draft"),
    ])


def test_unknown_event_raises():
    with pytest.raises(UnknownTransition):
        _machine().fire("explode")


def test_event_valid_from_another_state_raises():
    # "approve" exists, but not from "draft".
    with pytest.raises(UnknownTransition):
        _machine().fire("approve")


def test_rejected_guard_leaves_history_untouched():
    m = _machine()
    m.fire("submit")
    before = list(m.history)
    m.fire("approve", {"is_admin": False})
    assert m.history == before


def test_passing_guard_moves_the_machine():
    m = _machine()
    m.fire("submit")
    assert m.fire("approve", {"is_admin": True}) is True
    assert m.state == "published"


def test_history_records_each_move_in_order():
    m = _machine()
    m.fire("submit")
    m.fire("reject")
    assert m.history == ["draft", "review", "draft"]


def test_guard_receives_the_context():
    seen = {}
    m = Machine("a", [Transition("a", "go", "b", guard=lambda c: seen.update(c) or True)])
    m.fire("go", {"k": 1})
    assert seen == {"k": 1}


def test_guardless_transition_always_moves():
    m = Machine("a", [Transition("a", "go", "b")])
    assert m.fire("go") is True
    assert m.state == "b"
''',
        "fix": {
            "fsm/machine.py": '''\
from fsm.transitions import Transition, UnknownTransition


class Machine:
    def __init__(self, initial: str, transitions):
        self.state = initial
        self.transitions = list(transitions)
        self.history = [initial]

    def _find(self, event: str):
        for t in self.transitions:
            if t.source == self.state and t.event == event:
                return t
        return None

    def fire(self, event: str, ctx: dict | None = None) -> bool:
        """Apply `event`; returns True if the machine moved."""
        t = self._find(event)
        if t is None:
            raise UnknownTransition(f"no transition for {event!r} from {self.state!r}")
        # Consult the guard first: a rejected transition must leave both the
        # state and the history exactly as they were.
        if t.guard is not None and not t.guard(ctx or {}):
            return False
        self.state = t.target
        self.history.append(t.target)
        return True
''',
        },
    },
    # -------------------------------------------------------------- query filters
    {
        "id": "query-filter-compose",
        "problem": (
            "`query.compose` builds composite row filters out of the predicates in "
            "`query.predicates`. `any_of` matches every row regardless of its predicates, and "
            "`none_of` only consults the first predicate it is given. Fix both. Follow the "
            "usual conventions for empty inputs: `all_of()` and `none_of()` match everything, "
            "`any_of()` matches nothing."
        ),
        "files": {
            "query/__init__.py": "",
            "query/predicates.py": '''\
def eq(field, value):
    """Row's `field` equals `value`."""
    return lambda row: row.get(field) == value


def gt(field, value):
    """Row's `field` is present and greater than `value`."""
    return lambda row: row.get(field) is not None and row[field] > value


def contains(field, needle):
    """Row's `field` contains `needle` (missing fields never match)."""
    return lambda row: needle in (row.get(field) or "")
''',
            "query/compose.py": '''\
def all_of(*predicates):
    """Match rows satisfying every predicate."""
    def check(row):
        for p in predicates:
            if not p(row):
                return False
        return True
    return check


def any_of(*predicates):
    """Match rows satisfying at least one predicate."""
    def check(row):
        for p in predicates:
            if p(row):
                return True
        # BUG: falling through returns True, so any_of matches every row and
        # silently disables whatever filtering it was supposed to express.
        return True
    return check


def none_of(*predicates):
    """Match rows satisfying no predicate."""
    def check(row):
        # BUG: only the first predicate is negated; the rest are ignored.
        return not predicates[0](row) if predicates else True
    return check


def filter_rows(rows, predicate):
    return [r for r in rows if predicate(r)]
''',
        },
        "basic": '''\
from query.compose import all_of, any_of, filter_rows
from query.predicates import eq, gt

ROWS = [
    {"name": "ada", "age": 36},
    {"name": "bob", "age": 20},
    {"name": "cy", "age": 50},
]


def test_all_of():
    assert filter_rows(ROWS, all_of(gt("age", 30), eq("name", "ada"))) == [ROWS[0]]


def test_any_of_does_not_match_everything():
    got = filter_rows(ROWS, any_of(eq("name", "ada"), eq("name", "bob")))
    assert got == [ROWS[0], ROWS[1]]
''',
        "oracle": '''\
from query.compose import all_of, any_of, filter_rows, none_of
from query.predicates import contains, eq, gt

ROWS = [
    {"name": "ada", "age": 36},
    {"name": "bob", "age": 20},
    {"name": "cy", "age": 50},
]


def test_none_of_consults_every_predicate():
    got = filter_rows(ROWS, none_of(eq("name", "ada"), eq("name", "bob")))
    assert got == [ROWS[2]]


def test_any_of_with_no_matching_predicate():
    assert filter_rows(ROWS, any_of(eq("name", "zz"))) == []


def test_empty_any_of_matches_nothing():
    assert filter_rows(ROWS, any_of()) == []


def test_empty_all_of_matches_everything():
    assert filter_rows(ROWS, all_of()) == ROWS


def test_empty_none_of_matches_everything():
    assert filter_rows(ROWS, none_of()) == ROWS


def test_nested_composition():
    pred = all_of(gt("age", 25), any_of(eq("name", "ada"), eq("name", "cy")))
    assert filter_rows(ROWS, pred) == [ROWS[0], ROWS[2]]


def test_none_of_wrapping_a_composite():
    assert filter_rows(ROWS, none_of(any_of(eq("name", "ada"), eq("name", "cy")))) == [ROWS[1]]


def test_missing_fields_never_match():
    assert filter_rows(ROWS, contains("bio", "x")) == []
    assert filter_rows([{"name": "x"}], gt("age", 1)) == []
''',
        "fix": {
            "query/compose.py": '''\
def all_of(*predicates):
    """Match rows satisfying every predicate."""
    def check(row):
        for p in predicates:
            if not p(row):
                return False
        return True
    return check


def any_of(*predicates):
    """Match rows satisfying at least one predicate."""
    def check(row):
        for p in predicates:
            if p(row):
                return True
        # No predicate matched - and an empty any_of is vacuously false.
        return False
    return check


def none_of(*predicates):
    """Match rows satisfying no predicate."""
    inner = any_of(*predicates)

    def check(row):
        return not inner(row)
    return check


def filter_rows(rows, predicate):
    return [r for r in rows if predicate(r)]
''',
        },
    },
    # ------------------------------------------------------------------ patching
    {
        "id": "diff-hunk-offset",
        "problem": (
            "`patcher.apply.apply_hunks` applies a list of replacement hunks to a text. Each "
            "hunk's `start` refers to a line number in the *original* text, but applying a hunk "
            "that inserts or removes lines shifts every later line. No offset is tracked, so "
            "the second and subsequent hunks land in the wrong place whenever an earlier hunk "
            "changed the line count. Fix it. Hunks are applied in ascending `start` order "
            "regardless of the order given, and a hunk outside the text raises `PatchError`."
        ),
        "files": {
            "patcher/__init__.py": "",
            "patcher/hunk.py": '''\
from dataclasses import dataclass


class PatchError(Exception):
    """A hunk could not be applied."""


@dataclass(frozen=True)
class Hunk:
    """Replace `count` lines starting at 1-based `start` with `lines`."""

    start: int
    count: int
    lines: tuple
''',
            "patcher/apply.py": '''\
from patcher.hunk import Hunk, PatchError


def apply_hunks(text: str, hunks: list) -> str:
    """Apply `hunks` to `text`, returning the patched text."""
    lines = text.split("\\n")
    for hunk in sorted(hunks, key=lambda h: h.start):
        idx = hunk.start - 1
        if idx < 0 or idx + hunk.count > len(lines):
            raise PatchError(f"hunk at line {hunk.start} does not fit")
        # BUG: hunk positions refer to the original text, but each applied hunk
        # shifts everything after it by (len(lines) - count). That drift is
        # never accounted for, so every hunk after the first is misplaced as
        # soon as one of them changes the line count.
        lines[idx:idx + hunk.count] = list(hunk.lines)
    return "\\n".join(lines)
''',
        },
        "basic": '''\
from patcher.apply import apply_hunks
from patcher.hunk import Hunk

TEXT = "a\\nb\\nc\\nd\\ne"


def test_single_hunk():
    assert apply_hunks(TEXT, [Hunk(2, 1, ("B",))]) == "a\\nB\\nc\\nd\\ne"


def test_second_hunk_after_an_insertion():
    hunks = [Hunk(1, 1, ("A1", "A2")), Hunk(4, 1, ("D",))]
    assert apply_hunks(TEXT, hunks) == "A1\\nA2\\nb\\nc\\nD\\ne"
''',
        "oracle": '''\
import pytest

from patcher.apply import apply_hunks
from patcher.hunk import Hunk, PatchError

TEXT = "a\\nb\\nc\\nd\\ne"


def test_deletion_shifts_later_hunks():
    hunks = [Hunk(1, 3, ("X",)), Hunk(5, 1, ("E",))]
    assert apply_hunks(TEXT, hunks) == "X\\nd\\nE"


def test_three_hunks_growing_and_shrinking():
    hunks = [Hunk(1, 1, ("A", "A2")), Hunk(3, 1, ()), Hunk(5, 1, ("E",))]
    assert apply_hunks(TEXT, hunks) == "A\\nA2\\nb\\nd\\nE"


def test_input_order_does_not_matter():
    hunks = [Hunk(4, 1, ("D",)), Hunk(1, 1, ("A1", "A2"))]
    assert apply_hunks(TEXT, hunks) == "A1\\nA2\\nb\\nc\\nD\\ne"


def test_pure_deletion():
    assert apply_hunks(TEXT, [Hunk(2, 2, ())]) == "a\\nd\\ne"


def test_insertion_at_the_end():
    assert apply_hunks(TEXT, [Hunk(5, 1, ("e", "f"))]) == "a\\nb\\nc\\nd\\ne\\nf"


def test_out_of_range_hunk_raises():
    with pytest.raises(PatchError):
        apply_hunks(TEXT, [Hunk(10, 1, ("x",))])


def test_no_hunks_is_identity():
    assert apply_hunks(TEXT, []) == TEXT
''',
        "fix": {
            "patcher/apply.py": '''\
from patcher.hunk import Hunk, PatchError


def apply_hunks(text: str, hunks: list) -> str:
    """Apply `hunks` to `text`, returning the patched text."""
    lines = text.split("\\n")
    # Running drift between original line numbers and current ones.
    offset = 0
    for hunk in sorted(hunks, key=lambda h: h.start):
        idx = hunk.start - 1 + offset
        if idx < 0 or idx + hunk.count > len(lines):
            raise PatchError(f"hunk at line {hunk.start} does not fit")
        lines[idx:idx + hunk.count] = list(hunk.lines)
        offset += len(hunk.lines) - hunk.count
    return "\\n".join(lines)
''',
        },
    },
    # ------------------------------------------------------------ priority queue
    {
        "id": "priority-queue-tiebreak",
        "problem": (
            "`pqueue.queue.PriorityQueue` should pop the lowest priority value first, breaking "
            "ties by insertion order. It pushes `(priority, item)` tuples onto a heap, so "
            "whenever two priorities tie the heap compares the *items* themselves: "
            "equal-priority entries come out ordered by payload rather than insertion, and "
            "payloads that are not orderable (dicts, or mixed types) raise TypeError outright. "
            "Fix it so payloads are never compared."
        ),
        "files": {
            "pqueue/__init__.py": "",
            "pqueue/queue.py": '''\
import heapq


class PriorityQueue:
    """Lowest priority value pops first; ties pop in insertion order."""

    def __init__(self):
        self._heap = []

    def push(self, priority: int, item) -> None:
        # BUG: with only (priority, item) on the heap, any tie in priority falls
        # through to comparing `item` - which reorders equal-priority entries by
        # payload and blows up entirely on payloads that define no ordering.
        heapq.heappush(self._heap, (priority, item))

    def pop(self):
        if not self._heap:
            raise IndexError("pop from an empty queue")
        _priority, item = heapq.heappop(self._heap)
        return item

    def __len__(self) -> int:
        return len(self._heap)
''',
        },
        "basic": '''\
from pqueue.queue import PriorityQueue


def test_priority_order():
    q = PriorityQueue()
    q.push(2, "low")
    q.push(1, "high")
    assert q.pop() == "high"
    assert q.pop() == "low"


def test_ties_pop_in_insertion_order():
    q = PriorityQueue()
    q.push(1, "second")
    q.push(1, "first")
    assert q.pop() == "second"
    assert q.pop() == "first"
''',
        "oracle": '''\
import pytest

from pqueue.queue import PriorityQueue


def test_unorderable_payloads_are_never_compared():
    q = PriorityQueue()
    q.push(1, {"a": 1})
    q.push(1, {"b": 2})      # dicts define no ordering; this must not raise
    assert q.pop() == {"a": 1}
    assert q.pop() == {"b": 2}


def test_mixed_type_payloads():
    q = PriorityQueue()
    q.push(5, "text")
    q.push(5, 42)
    assert q.pop() == "text"
    assert q.pop() == 42


def test_stable_across_many_ties():
    q = PriorityQueue()
    for i in range(10):
        q.push(0, f"item{i}")
    assert [q.pop() for _ in range(10)] == [f"item{i}" for i in range(10)]


def test_interleaved_priorities_keep_within_level_order():
    q = PriorityQueue()
    q.push(2, "b1")
    q.push(1, "a1")
    q.push(2, "b2")
    q.push(1, "a2")
    assert [q.pop() for _ in range(4)] == ["a1", "a2", "b1", "b2"]


def test_len_tracks_contents():
    q = PriorityQueue()
    assert len(q) == 0
    q.push(1, "x")
    assert len(q) == 1
    q.pop()
    assert len(q) == 0


def test_pop_from_empty_raises():
    with pytest.raises(IndexError):
        PriorityQueue().pop()
''',
        "fix": {
            "pqueue/queue.py": '''\
import heapq
from itertools import count


class PriorityQueue:
    """Lowest priority value pops first; ties pop in insertion order."""

    def __init__(self):
        self._heap = []
        self._seq = count()

    def push(self, priority: int, item) -> None:
        # The monotonic counter breaks every tie before the payload is reached,
        # so heapq never needs the items to be orderable.
        heapq.heappush(self._heap, (priority, next(self._seq), item))

    def pop(self):
        if not self._heap:
            raise IndexError("pop from an empty queue")
        _priority, _seq, item = heapq.heappop(self._heap)
        return item

    def __len__(self) -> int:
        return len(self._heap)
''',
        },
    },
    # ----------------------------------------------------------------- url query
    {
        "id": "url-query-multivalue",
        "problem": (
            "`urlkit.encode` builds query strings that `urlkit.parse` reads back. Two bugs in "
            "the encoder: reserved characters are emitted raw, so a value containing `&` or `=` "
            "corrupts the query it sits in; and a list value is stringified whole instead of "
            "producing one repeated key per element. Fix `quote` to percent-encode anything "
            "outside the unreserved set as UTF-8 (space stays `+`), and `build_query` to emit "
            "`tag=a&tag=b` for a list."
        ),
        "files": {
            "urlkit/__init__.py": "",
            "urlkit/encode.py": '''\
_UNRESERVED = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_.~"
)


def quote(text: str) -> str:
    """Percent-encode `text` for use in a query string."""
    out = []
    for ch in text:
        if ch in _UNRESERVED:
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            # BUG: everything else is passed through unescaped, so a value
            # containing & or = silently corrupts the surrounding query string.
            out.append(ch)
    return "".join(out)


def build_query(params: dict) -> str:
    """Build a query string. A list value produces one pair per element."""
    parts = []
    for key, value in params.items():
        # BUG: a list is stringified as a whole rather than repeated, turning
        # {"tag": ["a", "b"]} into a single pair containing "['a', 'b']".
        parts.append(f"{quote(str(key))}={quote(str(value))}")
    return "&".join(parts)
''',
            "urlkit/parse.py": '''\
def unquote(text: str) -> str:
    """Reverse `quote`: decode %XX escapes and turn + back into a space."""
    text = text.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "%" and i + 3 <= len(text):
            try:
                out.append(int(text[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(text[i].encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


def parse_query(query: str) -> dict:
    """Parse a query string into {key: [values]}."""
    out: dict = {}
    if not query:
        return out
    for part in query.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        out.setdefault(unquote(key), []).append(unquote(value))
    return out
''',
        },
        "basic": '''\
from urlkit.encode import build_query, quote


def test_simple_pair():
    assert build_query({"q": "hello"}) == "q=hello"


def test_reserved_characters_are_escaped():
    assert quote("a&b") == "a%26b"
''',
        "oracle": '''\
from urlkit.encode import build_query, quote
from urlkit.parse import parse_query, unquote


def test_list_value_repeats_the_key():
    assert build_query({"tag": ["a", "b"]}) == "tag=a&tag=b"


def test_space_becomes_plus():
    assert build_query({"q": "hello world"}) == "q=hello+world"


def test_equals_in_value_is_escaped():
    assert build_query({"q": "a=b"}) == "q=a%3Db"


def test_round_trip_preserves_multivalue_and_reserved_chars():
    params = {"tag": ["x", "y"], "q": "a&b=c"}
    assert parse_query(build_query(params)) == {"tag": ["x", "y"], "q": ["a&b=c"]}


def test_round_trip_with_spaces():
    assert parse_query(build_query({"q": "hello world"})) == {"q": ["hello world"]}


def test_unicode_is_percent_encoded_as_utf8():
    assert quote("\\u00e9") == "%C3%A9"
    assert unquote("%C3%A9") == "\\u00e9"


def test_unreserved_characters_pass_through():
    assert quote("a-_.~Z9") == "a-_.~Z9"


def test_empty_inputs():
    assert build_query({}) == ""
    assert parse_query("") == {}
''',
        "fix": {
            "urlkit/encode.py": '''\
_UNRESERVED = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_.~"
)


def quote(text: str) -> str:
    """Percent-encode `text` for use in a query string."""
    out = []
    for ch in text:
        if ch in _UNRESERVED:
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            # Percent-encode per UTF-8 byte, so non-ASCII survives the round trip.
            for byte in ch.encode("utf-8"):
                out.append(f"%{byte:02X}")
    return "".join(out)


def build_query(params: dict) -> str:
    """Build a query string. A list value produces one pair per element."""
    parts = []
    for key, value in params.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            parts.append(f"{quote(str(key))}={quote(str(item))}")
    return "&".join(parts)
''',
        },
    },
    # -------------------------------------------------------------- markdown list
    {
        "id": "markdown-list-nesting",
        "problem": (
            "`mdlist` turns an indented markdown list into a tree. Two bugs across the two "
            "modules: `tokenize` counts a tab as a single column, so tab-indented items do not "
            "line up with space-indented ones (a tab should advance to the next 4-column tab "
            "stop); and `build_tree` pops only one level off its stack, so an item that dedents "
            "by more than one level is attached to the wrong parent instead of returning to the "
            "right one. Fix both."
        ),
        "files": {
            "mdlist/__init__.py": "",
            "mdlist/tokenize.py": '''\
from dataclasses import dataclass

TAB_WIDTH = 4


@dataclass(frozen=True)
class Item:
    indent: int   # indentation in columns
    text: str


def tokenize(source: str) -> list:
    """Extract list items, ignoring blank and non-list lines."""
    items = []
    for raw in source.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" \\t")
        if not stripped.startswith("- "):
            continue
        prefix = raw[: len(raw) - len(stripped)]
        # BUG: every prefix character counts as one column, so a tab measures 1
        # instead of advancing to the next TAB_WIDTH tab stop. Tab-indented
        # children then appear shallower than their space-indented parents.
        indent = len(prefix)
        items.append(Item(indent=indent, text=stripped[2:].strip()))
    return items
''',
            "mdlist/tree.py": '''\
from mdlist.tokenize import Item, tokenize


def build_tree(source: str) -> list:
    """Return nested nodes: {"text": ..., "children": [...]}."""
    items = tokenize(source)
    roots: list = []
    stack: list = []   # (indent, node) for the open ancestors
    for item in items:
        node = {"text": item.text, "children": []}
        # BUG: a single pop only closes one level, so an item that dedents past
        # several levels lands under whichever ancestor happens to be on top
        # rather than under its real parent.
        if stack and item.indent <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((item.indent, node))
    return roots
''',
        },
        "basic": '''\
from mdlist.tree import build_tree


def test_simple_nesting():
    tree = build_tree("- a\\n  - b")
    assert tree == [{"text": "a", "children": [{"text": "b", "children": []}]}]


def test_dedent_by_two_levels_returns_to_root():
    tree = build_tree("- a\\n  - b\\n    - c\\n- d")
    assert [n["text"] for n in tree] == ["a", "d"]
''',
        "oracle": '''\
from mdlist.tokenize import tokenize
from mdlist.tree import build_tree


def test_tab_advances_to_the_next_tab_stop():
    items = tokenize("- a\\n\\t- b")
    assert [i.indent for i in items] == [0, 4]


def test_tab_and_space_indentation_agree():
    tabbed = build_tree("- a\\n\\t- b")
    spaced = build_tree("- a\\n    - b")
    assert tabbed == spaced


def test_deep_dedent_keeps_the_full_subtree():
    tree = build_tree("- a\\n  - b\\n    - c\\n- d")
    assert len(tree) == 2
    assert tree[1] == {"text": "d", "children": []}
    assert tree[0]["children"][0]["children"][0]["text"] == "c"


def test_siblings_at_the_same_indent():
    assert [n["text"] for n in build_tree("- a\\n- b\\n- c")] == ["a", "b", "c"]


def test_dedent_to_an_intermediate_level():
    tree = build_tree("- a\\n  - b\\n    - c\\n  - d")
    assert [c["text"] for c in tree[0]["children"]] == ["b", "d"]


def test_blank_and_non_list_lines_are_ignored():
    tree = build_tree("intro\\n\\n- a\\nprose\\n  - b\\n")
    assert [n["text"] for n in tree] == ["a"]
    assert tree[0]["children"][0]["text"] == "b"


def test_empty_source():
    assert build_tree("") == []
''',
        "fix": {
            "mdlist/tokenize.py": '''\
from dataclasses import dataclass

TAB_WIDTH = 4


@dataclass(frozen=True)
class Item:
    indent: int   # indentation in columns
    text: str


def tokenize(source: str) -> list:
    """Extract list items, ignoring blank and non-list lines."""
    items = []
    for raw in source.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" \\t")
        if not stripped.startswith("- "):
            continue
        prefix = raw[: len(raw) - len(stripped)]
        indent = 0
        for ch in prefix:
            if ch == "\\t":
                # A tab advances to the next tab stop, not by one column.
                indent += TAB_WIDTH - (indent % TAB_WIDTH)
            else:
                indent += 1
        items.append(Item(indent=indent, text=stripped[2:].strip()))
    return items
''',
            "mdlist/tree.py": '''\
from mdlist.tokenize import Item, tokenize


def build_tree(source: str) -> list:
    """Return nested nodes: {"text": ..., "children": [...]}."""
    items = tokenize(source)
    roots: list = []
    stack: list = []   # (indent, node) for the open ancestors
    for item in items:
        node = {"text": item.text, "children": []}
        # Close every level the item has dedented past, not just one.
        while stack and item.indent <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((item.indent, node))
    return roots
''',
        },
    },
    # ---------------------------------------------------------------- inventory
    {
        "id": "inventory-reserve-oversell",
        "problem": (
            "`inventory.store.Store` tracks stock with reservations: `available` is on-hand "
            "minus reserved. Two bugs let the ledger report stock that does not exist. "
            "`reserve` checks the requested quantity against on-hand rather than against what "
            "is still available, so successive reservations can oversell the same units; and "
            "`release` subtracts unconditionally, so releasing more than was reserved drives "
            "the reserved count negative and inflates availability. Fix both."
        ),
        "files": {
            "inventory/__init__.py": "",
            "inventory/ledger.py": '''\
from dataclasses import dataclass


class InsufficientStock(Exception):
    """Not enough available stock to satisfy the request."""


@dataclass
class Entry:
    on_hand: int
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved
''',
            "inventory/store.py": '''\
from inventory.ledger import Entry, InsufficientStock


class Store:
    def __init__(self, stock: dict):
        self._items = {sku: Entry(on_hand=qty) for sku, qty in stock.items()}

    def available(self, sku: str) -> int:
        entry = self._items.get(sku)
        return entry.available if entry else 0

    def reserve(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        entry = self._items.get(sku)
        if entry is None:
            raise InsufficientStock(sku)
        # BUG: compares against on_hand, ignoring units already reserved, so a
        # second reservation can hand out stock the first one already claimed.
        if qty > entry.on_hand:
            raise InsufficientStock(sku)
        entry.reserved += qty

    def release(self, sku: str, qty: int) -> None:
        entry = self._items.get(sku)
        if entry is None:
            return
        # BUG: nothing floors this at zero, so an over-release makes `reserved`
        # negative and `available` larger than the stock that physically exists.
        entry.reserved -= qty

    def commit(self, sku: str, qty: int) -> None:
        """Ship reserved units: they leave both reserved and on_hand."""
        entry = self._items[sku]
        entry.reserved -= qty
        entry.on_hand -= qty
''',
        },
        "basic": '''\
import pytest

from inventory.ledger import InsufficientStock
from inventory.store import Store


def test_reserve_reduces_available():
    s = Store({"widget": 10})
    s.reserve("widget", 4)
    assert s.available("widget") == 6


def test_cannot_oversell_across_two_reservations():
    s = Store({"widget": 10})
    s.reserve("widget", 8)
    with pytest.raises(InsufficientStock):
        s.reserve("widget", 5)
''',
        "oracle": '''\
import pytest

from inventory.ledger import InsufficientStock
from inventory.store import Store


def test_over_release_cannot_inflate_availability():
    s = Store({"widget": 5})
    s.reserve("widget", 2)
    s.release("widget", 10)
    assert s.available("widget") == 5


def test_release_returns_units_for_reuse():
    s = Store({"widget": 5})
    s.reserve("widget", 3)
    s.release("widget", 3)
    assert s.available("widget") == 5
    s.reserve("widget", 5)
    assert s.available("widget") == 0


def test_reserving_exactly_what_is_available_succeeds():
    s = Store({"w": 4})
    s.reserve("w", 4)
    assert s.available("w") == 0


def test_commit_removes_units_from_on_hand():
    s = Store({"w": 5})
    s.reserve("w", 2)
    s.commit("w", 2)
    assert s.available("w") == 3


def test_availability_never_exceeds_on_hand():
    s = Store({"w": 3})
    s.reserve("w", 3)
    for _ in range(3):
        s.release("w", 1)
    s.release("w", 5)
    assert s.available("w") == 3


def test_unknown_sku():
    s = Store({"w": 1})
    assert s.available("nope") == 0
    with pytest.raises(InsufficientStock):
        s.reserve("nope", 1)


def test_non_positive_quantity_rejected():
    s = Store({"w": 1})
    with pytest.raises(ValueError):
        s.reserve("w", 0)
''',
        "fix": {
            "inventory/store.py": '''\
from inventory.ledger import Entry, InsufficientStock


class Store:
    def __init__(self, stock: dict):
        self._items = {sku: Entry(on_hand=qty) for sku, qty in stock.items()}

    def available(self, sku: str) -> int:
        entry = self._items.get(sku)
        return entry.available if entry else 0

    def reserve(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        entry = self._items.get(sku)
        if entry is None:
            raise InsufficientStock(sku)
        # Reserve against what is still free, not against gross stock.
        if qty > entry.available:
            raise InsufficientStock(sku)
        entry.reserved += qty

    def release(self, sku: str, qty: int) -> None:
        entry = self._items.get(sku)
        if entry is None:
            return
        # Floor at zero: you cannot un-reserve more than was reserved.
        entry.reserved = max(0, entry.reserved - qty)

    def commit(self, sku: str, qty: int) -> None:
        """Ship reserved units: they leave both reserved and on_hand."""
        entry = self._items[sku]
        entry.reserved -= qty
        entry.on_hand -= qty
''',
        },
    },
    # ----------------------------------------------------------- circuit breaker
    {
        "id": "circuit-breaker-reset",
        "problem": (
            "`breaker.circuit.CircuitBreaker` trips open after `threshold` consecutive "
            "failures and, once `reset_after` seconds have passed, allows a trial call in the "
            "half-open state. The failure counter is never cleared on success, so the count is "
            "cumulative rather than consecutive and the breaker eventually trips on an isolated "
            "failure; and a successful half-open trial leaves the breaker half-open instead of "
            "closing it. Fix both."
        ),
        "files": {
            "breaker/__init__.py": "",
            "breaker/clock.py": '''\
class ManualClock:
    """A hand-advanced clock so breaker timing is deterministic under test."""

    def __init__(self, now: float = 0.0):
        self._now = now

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
''',
            "breaker/circuit.py": '''\
from breaker.clock import ManualClock

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitOpen(Exception):
    """The circuit is open and the call was not attempted."""


class CircuitBreaker:
    def __init__(self, threshold: int = 3, reset_after: float = 10.0, clock=None):
        self.threshold = threshold
        self.reset_after = reset_after
        self.clock = clock or ManualClock()
        self.state = CLOSED
        self.failures = 0
        self._opened_at = None

    def call(self, fn):
        if self.state == OPEN:
            if self.clock.time() - self._opened_at >= self.reset_after:
                self.state = HALF_OPEN
            else:
                raise CircuitOpen("circuit is open")
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = OPEN
                self._opened_at = self.clock.time()
            raise
        # BUG: a success neither clears the failure counter - making the count
        # cumulative instead of consecutive - nor closes a half-open breaker,
        # which then stays half-open forever.
        return result
''',
        },
        "basic": '''\
import pytest

from breaker.circuit import CLOSED, OPEN, CircuitBreaker
from breaker.clock import ManualClock


def _boom():
    raise RuntimeError("x")


def test_opens_after_threshold_failures():
    b = CircuitBreaker(threshold=2, clock=ManualClock())
    for _ in range(2):
        with pytest.raises(RuntimeError):
            b.call(_boom)
    assert b.state == OPEN


def test_success_clears_the_failure_count():
    b = CircuitBreaker(threshold=2, clock=ManualClock())
    with pytest.raises(RuntimeError):
        b.call(_boom)
    b.call(lambda: "ok")
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state == CLOSED
''',
        "oracle": '''\
import pytest

from breaker.circuit import CLOSED, OPEN, CircuitBreaker, CircuitOpen
from breaker.clock import ManualClock


def _boom():
    raise RuntimeError("x")


def test_open_circuit_rejects_without_calling():
    b = CircuitBreaker(threshold=1, reset_after=10, clock=ManualClock())
    with pytest.raises(RuntimeError):
        b.call(_boom)
    with pytest.raises(CircuitOpen):
        b.call(lambda: "ok")


def test_successful_half_open_trial_closes_the_circuit():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(10)
    assert b.call(lambda: "ok") == "ok"
    assert b.state == CLOSED


def test_failed_half_open_trial_reopens():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(10)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state == OPEN


def test_failure_count_returns_to_zero_on_success():
    b = CircuitBreaker(threshold=3, clock=ManualClock())
    for _ in range(2):
        with pytest.raises(RuntimeError):
            b.call(_boom)
    b.call(lambda: "ok")
    assert b.failures == 0


def test_still_open_before_the_reset_window():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(9)
    with pytest.raises(CircuitOpen):
        b.call(lambda: "ok")


def test_closed_circuit_passes_the_result_through():
    assert CircuitBreaker(clock=ManualClock()).call(lambda: 42) == 42
''',
        "fix": {
            "breaker/circuit.py": '''\
from breaker.clock import ManualClock

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitOpen(Exception):
    """The circuit is open and the call was not attempted."""


class CircuitBreaker:
    def __init__(self, threshold: int = 3, reset_after: float = 10.0, clock=None):
        self.threshold = threshold
        self.reset_after = reset_after
        self.clock = clock or ManualClock()
        self.state = CLOSED
        self.failures = 0
        self._opened_at = None

    def call(self, fn):
        if self.state == OPEN:
            if self.clock.time() - self._opened_at >= self.reset_after:
                self.state = HALF_OPEN
            else:
                raise CircuitOpen("circuit is open")
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = OPEN
                self._opened_at = self.clock.time()
            raise
        # A success ends the failure streak, and a successful half-open trial
        # is the signal that the dependency has recovered.
        self.failures = 0
        self.state = CLOSED
        self._opened_at = None
        return result
''',
        },
    },
    # ------------------------------------------------------------- feature flags
    {
        "id": "feature-flag-override",
        "problem": (
            "`flags.rollout.FlagSet` decides whether a feature is on for a user, combining a "
            "percentage rollout (bucketed by the stable hash in `flags.hashing`) with per-user "
            "overrides. Overrides are only consulted when the percentage roll fails, so an "
            "explicit `False` override cannot switch a flag off for a user the rollout already "
            "includes; and the bucket comparison uses `<=`, so bucket 0 passes even at 0 "
            "percent. Fix both: an override always wins, and `percent` is the share of buckets "
            "strictly below it."
        ),
        "files": {
            "flags/__init__.py": "",
            "flags/hashing.py": '''\
import hashlib


def bucket_of(flag: str, user_id: str) -> int:
    """Stable bucket in [0, 100) for a (flag, user) pair."""
    digest = hashlib.sha256(f"{flag}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100
''',
            "flags/rollout.py": '''\
from flags.hashing import bucket_of


class FlagSet:
    def __init__(self, flags: dict):
        """flags: name -> {"percent": 0..100, "overrides": {user_id: bool}}"""
        self.flags = flags

    def is_enabled(self, flag: str, user_id: str) -> bool:
        spec = self.flags.get(flag)
        if spec is None:
            return False
        percent = spec.get("percent", 0)
        # BUG: `<=` admits bucket 0 even when percent is 0, so a flag that is
        # fully off still fires for one bucket's worth of users.
        if bucket_of(flag, user_id) <= percent:
            return True
        # BUG: overrides are only reached when the rollout says no, so an
        # explicit False override can never turn a flag off.
        return spec.get("overrides", {}).get(user_id, False)
''',
        },
        "basic": '''\
from flags.rollout import FlagSet


def test_zero_percent_is_off_for_everyone():
    fs = FlagSet({"beta": {"percent": 0}})
    assert not any(fs.is_enabled("beta", f"user{i}") for i in range(300))


def test_false_override_wins_over_the_rollout():
    fs = FlagSet({"beta": {"percent": 100, "overrides": {"vip": False}}})
    assert fs.is_enabled("beta", "vip") is False
''',
        "oracle": '''\
from flags.hashing import bucket_of
from flags.rollout import FlagSet


def test_true_override_wins_over_a_zero_rollout():
    fs = FlagSet({"beta": {"percent": 0, "overrides": {"vip": True}}})
    assert fs.is_enabled("beta", "vip") is True


def test_override_does_not_affect_other_users():
    fs = FlagSet({"beta": {"percent": 100, "overrides": {"vip": False}}})
    assert fs.is_enabled("beta", "someone-else") is True


def test_hundred_percent_is_on_for_everyone():
    fs = FlagSet({"beta": {"percent": 100}})
    assert all(fs.is_enabled("beta", f"user{i}") for i in range(100))


def test_bucketing_is_stable_across_calls():
    fs = FlagSet({"beta": {"percent": 50}})
    first = [fs.is_enabled("beta", f"u{i}") for i in range(100)]
    second = [fs.is_enabled("beta", f"u{i}") for i in range(100)]
    assert first == second


def test_buckets_stay_in_range():
    assert all(0 <= bucket_of("f", f"u{i}") < 100 for i in range(200))


def test_flags_bucket_independently():
    a = [bucket_of("alpha", f"u{i}") for i in range(50)]
    b = [bucket_of("beta", f"u{i}") for i in range(50)]
    assert a != b


def test_rollout_share_tracks_the_percentage():
    fs = FlagSet({"beta": {"percent": 30}})
    on = sum(fs.is_enabled("beta", f"u{i}") for i in range(2000))
    assert 500 <= on <= 700


def test_unknown_flag_is_off():
    assert FlagSet({}).is_enabled("nope", "u") is False
''',
        "fix": {
            "flags/rollout.py": '''\
from flags.hashing import bucket_of


class FlagSet:
    def __init__(self, flags: dict):
        """flags: name -> {"percent": 0..100, "overrides": {user_id: bool}}"""
        self.flags = flags

    def is_enabled(self, flag: str, user_id: str) -> bool:
        spec = self.flags.get(flag)
        if spec is None:
            return False
        # An override is an explicit decision and outranks the rollout in both
        # directions, so it is consulted before the bucket is computed.
        overrides = spec.get("overrides", {})
        if user_id in overrides:
            return overrides[user_id]
        # `percent` is the share of buckets strictly below it: at 0 nothing
        # qualifies, at 100 every bucket in [0, 100) does.
        return bucket_of(flag, user_id) < spec.get("percent", 0)
''',
        },
    },
    # ------------------------------------------------------------- log retention
    {
        "id": "log-rotate-retention",
        "problem": (
            "`logrotate` decides which rotated log files to delete. `sort_rotations` sorts "
            "filenames lexically, so `app.log.10` sorts before `app.log.2` once the index "
            "reaches double digits and retention then deletes the wrong files; and "
            "`files_to_delete` slices one past the retention limit, keeping one more file than "
            "asked. Fix both. Files with no rotation index are never deleted."
        ),
        "files": {
            "logrotate/__init__.py": "",
            "logrotate/naming.py": '''\
import re

_ROTATED = re.compile(r"^(?P<base>.+)\\.(?P<index>\\d+)$")


def rotated_name(base: str, index: int) -> str:
    return f"{base}.{index}"


def parse_index(filename: str):
    """Return the rotation index of `filename`, or None if it is not rotated."""
    m = _ROTATED.match(filename)
    return int(m.group("index")) if m else None


def sort_rotations(filenames: list) -> list:
    """Sort rotated files by age: index 1 is the most recent rotation."""
    # BUG: a lexical sort orders "app.log.10" before "app.log.2", so once the
    # index reaches two digits the notion of "oldest" is wrong.
    return sorted(filenames)
''',
            "logrotate/retention.py": '''\
from logrotate.naming import parse_index, sort_rotations


def files_to_delete(filenames: list, keep: int) -> list:
    """Return the rotated files that exceed the retention limit."""
    if keep < 0:
        raise ValueError("keep must be non-negative")
    rotated = [f for f in filenames if parse_index(f) is not None]
    ordered = sort_rotations(rotated)
    # BUG: slicing at keep + 1 retains one file more than requested.
    return ordered[keep + 1:]
''',
        },
        "basic": '''\
from logrotate.naming import sort_rotations
from logrotate.retention import files_to_delete


def test_sort_is_numeric_not_lexical():
    files = ["app.log.1", "app.log.2", "app.log.10"]
    assert sort_rotations(files) == ["app.log.1", "app.log.2", "app.log.10"]


def test_keeps_exactly_the_requested_number():
    files = ["app.log.1", "app.log.2", "app.log.3"]
    assert files_to_delete(files, keep=2) == ["app.log.3"]
''',
        "oracle": '''\
import pytest

from logrotate.naming import parse_index, rotated_name, sort_rotations
from logrotate.retention import files_to_delete


def test_double_digit_indices_order_correctly():
    files = [f"app.log.{i}" for i in (3, 11, 1, 22, 2)]
    assert sort_rotations(files) == [
        "app.log.1", "app.log.2", "app.log.3", "app.log.11", "app.log.22",
    ]


def test_retention_across_double_digits():
    files = [f"app.log.{i}" for i in range(1, 13)]
    assert files_to_delete(files, keep=3) == [f"app.log.{i}" for i in range(4, 13)]


def test_keep_zero_deletes_every_rotation():
    assert files_to_delete(["app.log.1", "app.log.2"], keep=0) == ["app.log.1", "app.log.2"]


def test_unrotated_files_are_never_deleted():
    files = ["app.log", "app.log.1", "app.log.2"]
    assert "app.log" not in files_to_delete(files, keep=0)


def test_keep_more_than_exists():
    assert files_to_delete(["app.log.1"], keep=5) == []


def test_parse_index():
    assert parse_index("app.log.7") == 7
    assert parse_index("app.log") is None
    assert parse_index(rotated_name("app.log", 4)) == 4


def test_negative_keep_rejected():
    with pytest.raises(ValueError):
        files_to_delete(["app.log.1"], keep=-1)
''',
        "fix": {
            "logrotate/naming.py": '''\
import re

_ROTATED = re.compile(r"^(?P<base>.+)\\.(?P<index>\\d+)$")


def rotated_name(base: str, index: int) -> str:
    return f"{base}.{index}"


def parse_index(filename: str):
    """Return the rotation index of `filename`, or None if it is not rotated."""
    m = _ROTATED.match(filename)
    return int(m.group("index")) if m else None


def sort_rotations(filenames: list) -> list:
    """Sort rotated files by age: index 1 is the most recent rotation."""
    def key(filename: str):
        index = parse_index(filename)
        # Unrotated names have no index; keep them first and stable by name.
        return (index is not None, index if index is not None else 0, filename)

    return sorted(filenames, key=key)
''',
            "logrotate/retention.py": '''\
from logrotate.naming import parse_index, sort_rotations


def files_to_delete(filenames: list, keep: int) -> list:
    """Return the rotated files that exceed the retention limit."""
    if keep < 0:
        raise ValueError("keep must be non-negative")
    rotated = [f for f in filenames if parse_index(f) is not None]
    ordered = sort_rotations(rotated)
    return ordered[keep:]
''',
        },
    },
]
