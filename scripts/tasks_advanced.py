"""The harder half of the local benchmark: multi-file, application-shaped bugs.

The original twelve tasks were single-file algorithm exercises (Roman numerals, RLE,
binary search). Two problems with that as an evaluation:

1. **Ceiling.** A 7B model solved 92% of them, which leaves almost no headroom for an
   ablation to move. A lever that looks worthless against a ceiling has not been
   measured, it has been hidden.
2. **Memorization.** Those problems appear verbatim in any code model's pretraining
   data, so a solve is partly recall. The fair criticism of the first version of this
   benchmark was that it measured retrieval of textbook algorithms, not agentic
   debugging.

The tasks here are deliberately different in kind: a small *package* rather than one
module, a bug that only shows at the seam between two files, and domain logic
(config merging, cache eviction, cursor pagination, permission inheritance) that has
no canonical published solution to recall. Localization is a real step — the agent
must find which of several files is wrong before it can fix anything.

Each task carries a `fix`: the known-good contents of the files it touches. Nothing
in the harness ever shows this to the agent; it exists so `validate_benchmark.py` can
prove the task is *solvable* rather than merely broken. A benchmark task that no
patch can fix scores zero forever and quietly drags down every condition equally.

Schema per task:
    id      - directory name under benchmarks/local/
    files   - {relative path: contents} written into workspace/ (the buggy code)
    problem - the statement handed to the agent
    basic   - workspace/test_basic.py, visible, and failing on the buggy code so the
              run_tests tool carries real signal
    oracle  - tests/test_oracle.py, hidden, checks the fix more thoroughly
    fix     - {relative path: contents} that makes the oracle pass (validation only)
"""

from __future__ import annotations

ADVANCED_TASKS: list[dict] = [
    # ------------------------------------------------------------------- config
    {
        "id": "config-layered-merge",
        "problem": (
            "The `conf` package applies configuration layers in order, with later layers "
            "overriding earlier ones. Nested sections are being clobbered: setting a single "
            "key inside a section drops that section's other keys. Fix the merge so nested "
            "dicts combine recursively, while non-dict values still replace. The merge must "
            "not mutate its inputs."
        ),
        "files": {
            "conf/__init__.py": "",
            "conf/merge.py": '''\
def deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` into `base`, returning a new dict."""
    out = dict(base)
    # BUG: dict.update replaces nested sections wholesale instead of merging
    # them, so {"db": {"port": 2}} wipes out db.host.
    out.update(override)
    return out
''',
            "conf/loader.py": '''\
from conf.merge import deep_merge


def load_layers(layers):
    """Apply config layers left to right; later layers win."""
    result: dict = {}
    for layer in layers:
        result = deep_merge(result, layer)
    return result
''',
        },
        "basic": '''\
from conf.loader import load_layers


def test_flat_override():
    assert load_layers([{"a": 1}, {"a": 2}]) == {"a": 2}


def test_nested_sibling_survives():
    layers = [{"db": {"host": "localhost", "port": 5432}}, {"db": {"port": 6000}}]
    assert load_layers(layers) == {"db": {"host": "localhost", "port": 6000}}
''',
        "oracle": '''\
from conf.loader import load_layers
from conf.merge import deep_merge


def test_three_layers_accumulate():
    layers = [{"a": {"x": 1, "y": 2}}, {"a": {"y": 3}}, {"a": {"z": 4}}]
    assert load_layers(layers) == {"a": {"x": 1, "y": 3, "z": 4}}


def test_deeply_nested():
    base = {"a": {"b": {"c": 1, "d": 2}}}
    assert deep_merge(base, {"a": {"b": {"d": 9}}}) == {"a": {"b": {"c": 1, "d": 9}}}


def test_non_dict_replaces_dict():
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


def test_dict_replaces_non_dict():
    assert deep_merge({"a": 5}, {"a": {"b": 1}}) == {"a": {"b": 1}}


def test_inputs_not_mutated():
    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    deep_merge(base, override)
    assert base == {"a": {"b": 1}}
    assert override == {"a": {"c": 2}}


def test_empty_layers():
    assert load_layers([]) == {}
''',
        "fix": {
            "conf/merge.py": '''\
def deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` into `base`, returning a new dict."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out
''',
        },
    },
    # -------------------------------------------------------------------- retry
    {
        "id": "retry-attempt-budget",
        "problem": (
            "`retry.runner.call_with_retry` retries a failing function using the backoff "
            "schedule from `retry.policy`. Two things are wrong: the function is invoked one "
            "more time than `max_attempts` allows, and the backoff grows without bound "
            "instead of being capped at `max_delay`. Fix both. A successful call must not "
            "sleep at all, and the last failure's exception should propagate."
        ),
        "files": {
            "retry/__init__.py": "",
            "retry/policy.py": '''\
from dataclasses import dataclass


@dataclass
class Policy:
    max_attempts: int = 3
    base_delay: float = 0.01
    factor: float = 2.0
    max_delay: float = 0.05

    def delay_for(self, attempt: int) -> float:
        """Delay before retry number `attempt` (0-based)."""
        # BUG: the computed delay is never clamped to max_delay.
        return self.base_delay * (self.factor ** attempt)
''',
            "retry/runner.py": '''\
import time

from retry.policy import Policy


def call_with_retry(fn, policy: Policy | None = None):
    """Call `fn`, retrying on exception according to `policy`.

    Returns fn's result, or re-raises the final exception once attempts run out.
    """
    policy = policy or Policy()
    last_exc = None
    # BUG: range(max_attempts + 1) runs one extra attempt.
    for attempt in range(policy.max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(policy.delay_for(attempt))
    raise last_exc
''',
        },
        "basic": '''\
from retry.policy import Policy
from retry.runner import call_with_retry


def test_attempt_count():
    calls = []

    def boom():
        calls.append(1)
        raise ValueError("nope")

    try:
        call_with_retry(boom, Policy(max_attempts=3))
    except ValueError:
        pass
    assert len(calls) == 3


def test_delay_capped():
    p = Policy(base_delay=0.01, factor=2.0, max_delay=0.05)
    assert p.delay_for(10) == 0.05
''',
        "oracle": '''\
import pytest

from retry.policy import Policy
from retry.runner import call_with_retry


def test_success_first_try_no_retry():
    calls = []

    def ok():
        calls.append(1)
        return "fine"

    assert call_with_retry(ok, Policy(max_attempts=3)) == "fine"
    assert len(calls) == 1


def test_succeeds_on_last_allowed_attempt():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("not yet")
        return "ok"

    assert call_with_retry(flaky, Policy(max_attempts=3)) == "ok"
    assert len(calls) == 3


def test_single_attempt_means_no_retry():
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        call_with_retry(boom, Policy(max_attempts=1))
    assert len(calls) == 1


def test_final_exception_propagates():
    def boom():
        raise KeyError("last")

    with pytest.raises(KeyError):
        call_with_retry(boom, Policy(max_attempts=2))


def test_delay_schedule_grows_then_caps():
    p = Policy(base_delay=0.01, factor=2.0, max_delay=0.05)
    assert p.delay_for(0) == pytest.approx(0.01)
    assert p.delay_for(1) == pytest.approx(0.02)
    assert p.delay_for(2) == pytest.approx(0.04)
    assert p.delay_for(3) == pytest.approx(0.05)
    assert p.delay_for(50) == pytest.approx(0.05)
''',
        "fix": {
            "retry/policy.py": '''\
from dataclasses import dataclass


@dataclass
class Policy:
    max_attempts: int = 3
    base_delay: float = 0.01
    factor: float = 2.0
    max_delay: float = 0.05

    def delay_for(self, attempt: int) -> float:
        """Delay before retry number `attempt` (0-based)."""
        return min(self.base_delay * (self.factor ** attempt), self.max_delay)
''',
            "retry/runner.py": '''\
import time

from retry.policy import Policy


def call_with_retry(fn, policy: Policy | None = None):
    """Call `fn`, retrying on exception according to `policy`.

    Returns fn's result, or re-raises the final exception once attempts run out.
    """
    policy = policy or Policy()
    last_exc = None
    for attempt in range(policy.max_attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < policy.max_attempts - 1:
                time.sleep(policy.delay_for(attempt))
    raise last_exc
''',
        },
    },
    # -------------------------------------------------------------------- cache
    {
        "id": "lru-cache-ttl-expiry",
        "problem": (
            "`cache.store.TTLCache` is an LRU cache with per-entry expiry, using the injectable "
            "clock in `cache.clock`. Expired entries are still being returned by `get`, and "
            "eviction picks the wrong victim because reads do not refresh recency. Fix both so "
            "that an expired key behaves exactly like a missing key, and eviction removes the "
            "least *recently used* entry."
        ),
        "files": {
            "cache/__init__.py": "",
            "cache/clock.py": '''\
class ManualClock:
    """A clock the tests advance by hand, so expiry is deterministic."""

    def __init__(self, now: float = 0.0):
        self._now = now

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
''',
            "cache/store.py": '''\
from collections import OrderedDict

from cache.clock import ManualClock

MISSING = object()


class TTLCache:
    def __init__(self, capacity: int, ttl: float, clock=None):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock or ManualClock()
        self._data: OrderedDict = OrderedDict()

    def set(self, key, value) -> None:
        self._data[key] = (value, self.clock.time())
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            # Evict the oldest entry.
            self._data.popitem(last=False)

    def get(self, key, default=None):
        entry = self._data.get(key, MISSING)
        if entry is MISSING:
            return default
        value, _stored_at = entry
        # BUG: the stored timestamp is never compared against the TTL, so expired
        # entries are served indefinitely. BUG: a hit does not refresh recency,
        # so the LRU order reflects insertion order only.
        return value

    def __len__(self) -> int:
        return len(self._data)
''',
        },
        "basic": '''\
from cache.clock import ManualClock
from cache.store import TTLCache


def test_hit_before_expiry():
    c = TTLCache(capacity=2, ttl=10, clock=ManualClock())
    c.set("a", 1)
    assert c.get("a") == 1


def test_expired_entry_is_a_miss():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(11)
    assert c.get("a") is None
''',
        "oracle": '''\
from cache.clock import ManualClock
from cache.store import TTLCache


def test_expiry_boundary_is_exclusive():
    clock = ManualClock()
    c = TTLCache(capacity=4, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(10)
    # Exactly at the TTL the entry is still considered fresh.
    assert c.get("a") == 1
    clock.advance(0.001)
    assert c.get("a") is None


def test_expired_entry_respects_default():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=5, clock=clock)
    c.set("a", 1)
    clock.advance(6)
    assert c.get("a", "gone") == "gone"


def test_read_refreshes_recency():
    c = TTLCache(capacity=2, ttl=100, clock=ManualClock())
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")          # "a" is now the most recently used
    c.set("c", 3)       # evicts the least recently used, which is "b"
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_capacity_enforced():
    c = TTLCache(capacity=2, ttl=100, clock=ManualClock())
    for k in "abc":
        c.set(k, k)
    assert len(c) == 2


def test_overwrite_refreshes_timestamp():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(8)
    c.set("a", 2)
    clock.advance(5)
    assert c.get("a") == 2
''',
        "fix": {
            "cache/store.py": '''\
from collections import OrderedDict

from cache.clock import ManualClock

MISSING = object()


class TTLCache:
    def __init__(self, capacity: int, ttl: float, clock=None):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock or ManualClock()
        self._data: OrderedDict = OrderedDict()

    def set(self, key, value) -> None:
        self._data[key] = (value, self.clock.time())
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def get(self, key, default=None):
        entry = self._data.get(key, MISSING)
        if entry is MISSING:
            return default
        value, stored_at = entry
        if self.clock.time() - stored_at > self.ttl:
            del self._data[key]
            return default
        self._data.move_to_end(key)
        return value

    def __len__(self) -> int:
        return len(self._data)
''',
        },
    },
    # --------------------------------------------------------------- pagination
    {
        "id": "cursor-pagination-boundary",
        "problem": (
            "`api.paginate.page` returns a slice of records plus a cursor for the next page. "
            "Paging through a collection currently repeats one record at every page boundary, "
            "and the final page reports a next-cursor even though nothing follows. Fix it so "
            "that walking the cursors yields every record exactly once and the last page "
            "returns a next-cursor of None."
        ),
        "files": {
            "api/__init__.py": "",
            "api/models.py": '''\
from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    items: list
    next_cursor: int | None
''',
            "api/paginate.py": '''\
from api.models import Page


def page(records, cursor: int = 0, limit: int = 2) -> Page:
    """Return `limit` records starting at `cursor`, plus the cursor to continue from."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    window = records[cursor:cursor + limit]
    # BUG: the next cursor points at the last item returned rather than past it,
    # so the following page repeats that record. BUG: a next cursor is emitted
    # even when the window reached the end of the collection.
    next_cursor = cursor + limit - 1
    return Page(items=window, next_cursor=next_cursor)


def walk(records, limit: int = 2):
    """Yield every record by following cursors to exhaustion."""
    cursor: int | None = 0
    while cursor is not None:
        p = page(records, cursor, limit)
        yield from p.items
        if p.next_cursor is not None:
            # Two ways a broken cursor loops forever: it stops advancing, or it
            # runs off the end and keeps handing back empty pages. Neither should
            # hang a caller, so both fail loudly.
            if p.next_cursor <= cursor:
                raise RuntimeError(f"cursor did not advance past {cursor}")
            if not p.items:
                raise RuntimeError(f"empty page at cursor {cursor} with more promised")
        cursor = p.next_cursor
''',
        },
        "basic": '''\
from api.paginate import page, walk


def test_first_page():
    p = page([1, 2, 3, 4, 5], cursor=0, limit=2)
    assert p.items == [1, 2]
    assert p.next_cursor == 2


def test_walk_yields_each_once():
    assert list(walk([1, 2, 3, 4, 5], limit=2)) == [1, 2, 3, 4, 5]
''',
        "oracle": '''\
import pytest

from api.paginate import page, walk


def test_last_page_has_no_cursor():
    p = page([1, 2, 3, 4], cursor=2, limit=2)
    assert p.items == [3, 4]
    assert p.next_cursor is None


def test_exact_multiple_terminates():
    assert list(walk([1, 2, 3, 4], limit=2)) == [1, 2, 3, 4]


def test_ragged_final_page():
    p = page([1, 2, 3], cursor=2, limit=2)
    assert p.items == [3]
    assert p.next_cursor is None


def test_empty_collection():
    p = page([], cursor=0, limit=3)
    assert p.items == []
    assert p.next_cursor is None
    assert list(walk([], limit=3)) == []


def test_limit_larger_than_collection():
    p = page([1, 2], cursor=0, limit=10)
    assert p.items == [1, 2]
    assert p.next_cursor is None


def test_limit_of_one():
    assert list(walk([1, 2, 3], limit=1)) == [1, 2, 3]


def test_invalid_limit_rejected():
    with pytest.raises(ValueError):
        page([1, 2], cursor=0, limit=0)
''',
        "fix": {
            "api/paginate.py": '''\
from api.models import Page


def page(records, cursor: int = 0, limit: int = 2) -> Page:
    """Return `limit` records starting at `cursor`, plus the cursor to continue from."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    window = records[cursor:cursor + limit]
    end = cursor + len(window)
    next_cursor = end if end < len(records) else None
    return Page(items=window, next_cursor=next_cursor)


def walk(records, limit: int = 2):
    """Yield every record by following cursors to exhaustion."""
    cursor: int | None = 0
    while cursor is not None:
        p = page(records, cursor, limit)
        yield from p.items
        if p.next_cursor is not None:
            # Two ways a broken cursor loops forever: it stops advancing, or it
            # runs off the end and keeps handing back empty pages. Neither should
            # hang a caller, so both fail loudly.
            if p.next_cursor <= cursor:
                raise RuntimeError(f"cursor did not advance past {cursor}")
            if not p.items:
                raise RuntimeError(f"empty page at cursor {cursor} with more promised")
        cursor = p.next_cursor
''',
        },
    },
    # --------------------------------------------------------------- event bus
    {
        "id": "event-bus-unsubscribe",
        "problem": (
            "`events.bus.EventBus` dispatches an event to subscribed handlers in priority order "
            "(higher priority first). Two defects: handlers registered with equal priority run "
            "in reverse registration order instead of registration order, and a handler that "
            "unsubscribes itself during dispatch causes later handlers to be skipped. Fix both."
        ),
        "files": {
            "events/__init__.py": "",
            "events/bus.py": '''\
class EventBus:
    def __init__(self):
        # list of (priority, handler)
        self._handlers: list[tuple[int, object]] = []

    def subscribe(self, handler, priority: int = 0) -> None:
        # BUG: inserting at the front means that among handlers of equal
        # priority the most recently registered runs first, reversing
        # registration order. The stable sort below preserves that inversion.
        self._handlers.insert(0, (priority, handler))
        self._handlers.sort(key=lambda pair: -pair[0])

    def unsubscribe(self, handler) -> None:
        # BUG: removing in place mutates the very list publish() is iterating.
        for i, (_p, h) in enumerate(self._handlers):
            if h is handler:
                del self._handlers[i]
                break

    def publish(self, event) -> list:
        results = []
        # BUG: iterating the live list while a handler removes itself shifts the
        # remaining items down and skips the next one.
        for _priority, handler in self._handlers:
            results.append(handler(event))
        return results
''',
        },
        "basic": '''\
from events.bus import EventBus


def test_priority_order():
    bus = EventBus()
    bus.subscribe(lambda e: "low", priority=0)
    bus.subscribe(lambda e: "high", priority=10)
    assert bus.publish("x") == ["high", "low"]


def test_equal_priority_keeps_registration_order():
    bus = EventBus()
    bus.subscribe(lambda e: "first", priority=0)
    bus.subscribe(lambda e: "second", priority=0)
    assert bus.publish("x") == ["first", "second"]
''',
        "oracle": '''\
from events.bus import EventBus


def test_self_unsubscribe_does_not_skip_others():
    bus = EventBus()
    seen = []

    def once(event):
        seen.append("once")
        bus.unsubscribe(once)
        return "once"

    bus.subscribe(once, priority=5)
    bus.subscribe(lambda e: seen.append("after") or "after", priority=1)

    assert bus.publish("x") == ["once", "after"]
    assert seen == ["once", "after"]
    # Second publish sees only the surviving handler.
    seen.clear()
    assert bus.publish("y") == ["after"]


def test_three_equal_priorities_in_order():
    bus = EventBus()
    for name in ("a", "b", "c"):
        bus.subscribe(lambda e, n=name: n, priority=0)
    assert bus.publish("x") == ["a", "b", "c"]


def test_mixed_priorities_stable_within_level():
    bus = EventBus()
    bus.subscribe(lambda e: "lo1", priority=0)
    bus.subscribe(lambda e: "hi1", priority=9)
    bus.subscribe(lambda e: "lo2", priority=0)
    bus.subscribe(lambda e: "hi2", priority=9)
    assert bus.publish("x") == ["hi1", "hi2", "lo1", "lo2"]


def test_unsubscribe_unknown_handler_is_noop():
    bus = EventBus()
    bus.subscribe(lambda e: "a")
    bus.unsubscribe(lambda e: "other")
    assert bus.publish("x") == ["a"]


def test_publish_with_no_handlers():
    assert EventBus().publish("x") == []
''',
        "fix": {
            "events/bus.py": '''\
from itertools import count


class EventBus:
    def __init__(self):
        # list of (priority, sequence, handler); sequence preserves registration
        # order among equal priorities.
        self._handlers: list[tuple[int, int, object]] = []
        self._seq = count()

    def subscribe(self, handler, priority: int = 0) -> None:
        self._handlers.append((priority, next(self._seq), handler))
        self._handlers.sort(key=lambda triple: (-triple[0], triple[1]))

    def unsubscribe(self, handler) -> None:
        self._handlers = [t for t in self._handlers if t[2] is not handler]

    def publish(self, event) -> list:
        results = []
        # Iterate a snapshot so handlers may subscribe/unsubscribe during dispatch.
        for _priority, _seq, handler in list(self._handlers):
            results.append(handler(event))
        return results
''',
        },
    },
    # ------------------------------------------------------------------- semver
    {
        "id": "semver-prerelease-order",
        "problem": (
            "`semver` parses and compares versions. Comparison is wrong in two ways: a version "
            "with a prerelease tag (1.0.0-alpha) is treated as *newer* than the matching release "
            "(1.0.0) when it must be older, and numeric prerelease identifiers are compared as "
            "strings so 1.0.0-2 sorts before 1.0.0-10. Fix `compare` to follow semver precedence."
        ),
        "files": {
            "semver/__init__.py": "",
            "semver/parse.py": '''\
import re
from dataclasses import dataclass

_PATTERN = re.compile(r"^(\\d+)\\.(\\d+)\\.(\\d+)(?:-([0-9A-Za-z.-]+))?$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple = ()


def parse(text: str) -> Version:
    m = _PATTERN.match(text.strip())
    if not m:
        raise ValueError(f"not a version: {text!r}")
    major, minor, patch, pre = m.groups()
    parts = tuple(pre.split(".")) if pre else ()
    return Version(int(major), int(minor), int(patch), parts)
''',
            "semver/compare.py": '''\
from semver.parse import Version, parse


def _key(v: Version):
    # BUG: prerelease identifiers are compared as raw strings, so "10" < "2",
    # and an empty prerelease tuple sorts *before* a populated one, making
    # 1.0.0 older than 1.0.0-alpha. Semver requires the opposite.
    return (v.major, v.minor, v.patch, v.prerelease)


def compare(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b."""
    ka, kb = _key(parse(a)), _key(parse(b))
    if ka < kb:
        return -1
    return 0 if ka == kb else 1
''',
        },
        "basic": '''\
from semver.compare import compare


def test_patch_order():
    assert compare("1.0.1", "1.0.0") == 1


def test_prerelease_is_older_than_release():
    assert compare("1.0.0-alpha", "1.0.0") == -1
''',
        "oracle": '''\
import pytest

from semver.compare import compare
from semver.parse import parse


def test_numeric_identifiers_compare_numerically():
    assert compare("1.0.0-2", "1.0.0-10") == -1


def test_numeric_lower_than_alphanumeric():
    assert compare("1.0.0-1", "1.0.0-alpha") == -1


def test_more_identifiers_wins_when_prefix_equal():
    assert compare("1.0.0-alpha", "1.0.0-alpha.1") == -1


def test_documented_precedence_chain():
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    for lo, hi in zip(chain, chain[1:]):
        assert compare(lo, hi) == -1, f"{lo} should precede {hi}"
        assert compare(hi, lo) == 1


def test_equality():
    assert compare("2.3.4", "2.3.4") == 0
    assert compare("2.3.4-rc.1", "2.3.4-rc.1") == 0


def test_major_minor_dominate():
    assert compare("2.0.0", "1.99.99") == 1
    assert compare("1.2.0", "1.1.99") == 1


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse("not.a.version")
''',
        "fix": {
            "semver/compare.py": '''\
from semver.parse import Version, parse


def _identifier_key(part: str):
    # Numeric identifiers compare numerically and always rank below
    # alphanumeric ones; the leading flag encodes that ordering.
    if part.isdigit():
        return (0, int(part), "")
    return (1, 0, part)


def _key(v: Version):
    # A release has no prerelease and outranks any prerelease of the same
    # version, so the presence flag is 1 for releases and 0 otherwise.
    has_release = 0 if v.prerelease else 1
    return (
        v.major,
        v.minor,
        v.patch,
        has_release,
        tuple(_identifier_key(p) for p in v.prerelease),
    )


def compare(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b."""
    ka, kb = _key(parse(a)), _key(parse(b))
    if ka < kb:
        return -1
    return 0 if ka == kb else 1
''',
        },
    },
    # ------------------------------------------------------------- rate limiter
    {
        "id": "rate-limit-sliding-window",
        "problem": (
            "`limits.window.SlidingWindow` should allow at most `limit` calls in any rolling "
            "`window` seconds, using the injectable clock from `limits.clock`. It currently "
            "behaves like a fixed window that resets on a boundary, which lets through up to "
            "twice the limit across a boundary. Rewrite `allow` to enforce a true sliding "
            "window: a call is permitted only if fewer than `limit` calls occurred in the "
            "preceding `window` seconds."
        ),
        "files": {
            "limits/__init__.py": "",
            "limits/clock.py": '''\
class ManualClock:
    """A hand-advanced clock so limiter behavior is deterministic under test."""

    def __init__(self, now: float = 0.0):
        self._now = now

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
''',
            "limits/window.py": '''\
from limits.clock import ManualClock


class SlidingWindow:
    def __init__(self, limit: int, window: float, clock=None):
        self.limit = limit
        self.window = window
        self.clock = clock or ManualClock()
        self._count = 0
        self._bucket_start = self.clock.time()

    def allow(self) -> bool:
        """Return True if a call is permitted now, recording it if so."""
        now = self.clock.time()
        # BUG: this is a fixed window. The counter resets wholesale once the
        # bucket elapses, so `limit` calls at the end of one bucket plus `limit`
        # at the start of the next both succeed - 2x the intended rate.
        if now - self._bucket_start >= self.window:
            self._bucket_start = now
            self._count = 0
        if self._count < self.limit:
            self._count += 1
            return True
        return False
''',
        },
        "basic": '''\
from limits.clock import ManualClock
from limits.window import SlidingWindow


def test_allows_up_to_limit():
    w = SlidingWindow(limit=2, window=10, clock=ManualClock())
    assert w.allow() is True
    assert w.allow() is True
    assert w.allow() is False


def test_no_double_rate_across_boundary():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    clock.advance(9)
    assert w.allow() is True
    assert w.allow() is True
    clock.advance(1.5)   # old calls are still within the rolling 10s window
    assert w.allow() is False
''',
        "oracle": '''\
from limits.clock import ManualClock
from limits.window import SlidingWindow


def test_calls_expire_out_of_window():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    assert w.allow() is True
    assert w.allow() is True
    assert w.allow() is False
    clock.advance(10.1)
    assert w.allow() is True


def test_partial_expiry_frees_one_slot():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    assert w.allow() is True
    clock.advance(5)
    assert w.allow() is True
    assert w.allow() is False
    clock.advance(5.1)      # the first call has aged out, the second has not
    assert w.allow() is True
    assert w.allow() is False


def test_limit_of_one():
    clock = ManualClock()
    w = SlidingWindow(limit=1, window=5, clock=clock)
    assert w.allow() is True
    clock.advance(4.9)
    assert w.allow() is False
    clock.advance(0.2)
    assert w.allow() is True


def test_steady_state_rate_is_capped():
    clock = ManualClock()
    w = SlidingWindow(limit=3, window=10, clock=clock)
    allowed = 0
    for _ in range(100):
        if w.allow():
            allowed += 1
        clock.advance(1)
    # 100 seconds at 3 per rolling 10s is ~30 calls, never 2x that.
    assert 28 <= allowed <= 32
''',
        "fix": {
            "limits/window.py": '''\
from collections import deque

from limits.clock import ManualClock


class SlidingWindow:
    def __init__(self, limit: int, window: float, clock=None):
        self.limit = limit
        self.window = window
        self.clock = clock or ManualClock()
        self._calls: deque = deque()

    def allow(self) -> bool:
        """Return True if a call is permitted now, recording it if so."""
        now = self.clock.time()
        cutoff = now - self.window
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()
        if len(self._calls) < self.limit:
            self._calls.append(now)
            return True
        return False
''',
        },
    },
    # ---------------------------------------------------------------------- csv
    {
        "id": "csv-quoted-fields",
        "problem": (
            "`csvlite.reader.parse_line` splits a single CSV line into fields. It handles plain "
            "fields but breaks on quoting: a comma inside a quoted field splits it in two, and "
            "a doubled quote (\"\") inside a quoted field should produce one literal quote "
            "character rather than terminating the field. Fix the parser. Surrounding quotes "
            "are not part of the value."
        ),
        "files": {
            "csvlite/__init__.py": "",
            "csvlite/reader.py": '''\
def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields, honoring double-quoted fields."""
    # BUG: a naive split ignores quoting entirely, so quoted fields containing
    # commas are torn apart and the quote characters are left in the values.
    return line.split(",")


def parse(text: str) -> list[list[str]]:
    """Parse a whole CSV document into rows of fields."""
    return [parse_line(line) for line in text.splitlines() if line]
''',
        },
        "basic": '''\
from csvlite.reader import parse_line


def test_plain_fields():
    assert parse_line("a,b,c") == ["a", "b", "c"]


def test_quoted_field_with_comma():
    assert parse_line('a,"b,c",d') == ["a", "b,c", "d"]
''',
        "oracle": '''\
from csvlite.reader import parse, parse_line


def test_escaped_quote_inside_quoted_field():
    assert parse_line('a,"say ""hi""",b') == ["a", 'say "hi"', "b"]


def test_quoted_field_only():
    assert parse_line('"hello"') == ["hello"]


def test_empty_fields_preserved():
    assert parse_line("a,,b") == ["a", "", "b"]
    assert parse_line(",") == ["", ""]


def test_empty_quoted_field():
    assert parse_line('a,"",b') == ["a", "", "b"]


def test_quote_not_at_field_start_is_literal():
    assert parse_line("a,b\\"c,d") == ["a", 'b"c', "d"]


def test_trailing_quoted_field():
    assert parse_line('a,"b,c"') == ["a", "b,c"]


def test_multiple_rows():
    doc = 'name,note\\nalice,"likes a,b"\\nbob,plain'
    assert parse(doc) == [["name", "note"], ["alice", "likes a,b"], ["bob", "plain"]]
''',
        "fix": {
            "csvlite/reader.py": '''\
def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields, honoring double-quoted fields."""
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                # A doubled quote inside a quoted field is one literal quote.
                if i + 1 < len(line) and line[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                in_quotes = False
            else:
                current.append(ch)
        else:
            if ch == '"' and not current:
                # Quotes only open a field at its start; elsewhere they are literal.
                in_quotes = True
            elif ch == ",":
                fields.append("".join(current))
                current = []
            else:
                current.append(ch)
        i += 1
    fields.append("".join(current))
    return fields


def parse(text: str) -> list[list[str]]:
    """Parse a whole CSV document into rows of fields."""
    return [parse_line(line) for line in text.splitlines() if line]
''',
        },
    },
    # ----------------------------------------------------------- dep resolution
    {
        "id": "dep-resolve-cycles",
        "problem": (
            "`deps.resolve.resolve_order` returns the order in which packages must be installed, "
            "given each package's dependencies. Two bugs: a dependency reached by more than one "
            "path (a diamond) is emitted twice, and a dependency cycle causes infinite recursion "
            "instead of raising `CycleError`. Fix both. Dependencies must appear before the "
            "packages that require them."
        ),
        "files": {
            "deps/__init__.py": "",
            "deps/graph.py": '''\
class CycleError(Exception):
    """Raised when the dependency graph cannot be linearized."""

    def __init__(self, node):
        super().__init__(f"dependency cycle involving {node!r}")
        self.node = node


class Graph:
    def __init__(self, edges: dict[str, list[str]]):
        # node -> list of nodes it depends on
        self.edges = {k: list(v) for k, v in edges.items()}

    def deps_of(self, node: str) -> list[str]:
        return self.edges.get(node, [])

    def nodes(self) -> list[str]:
        seen = list(self.edges)
        for targets in self.edges.values():
            for t in targets:
                if t not in seen:
                    seen.append(t)
        return seen
''',
            "deps/resolve.py": '''\
from deps.graph import CycleError, Graph


def resolve_order(edges: dict[str, list[str]]) -> list[str]:
    """Return an install order: every dependency precedes its dependent."""
    graph = Graph(edges)
    order: list[str] = []

    def visit(node: str):
        # BUG: nothing records which nodes have already been emitted, so a node
        # reachable by two paths is appended twice. BUG: nothing tracks the nodes
        # currently on the recursion stack, so a cycle recurses until Python
        # raises RecursionError instead of CycleError.
        for dep in graph.deps_of(node):
            visit(dep)
        order.append(node)

    for node in graph.nodes():
        visit(node)
    return order
''',
        },
        "basic": '''\
import pytest

from deps.graph import CycleError
from deps.resolve import resolve_order


def test_linear_chain():
    assert resolve_order({"app": ["lib"], "lib": []}) == ["lib", "app"]


def test_diamond_has_no_duplicates():
    order = resolve_order({"app": ["a", "b"], "a": ["base"], "b": ["base"], "base": []})
    assert order.count("base") == 1
    assert len(order) == len(set(order))


def test_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["b"], "b": ["a"]})
''',
        "oracle": '''\
import pytest

from deps.graph import CycleError
from deps.resolve import resolve_order


def _precedes(order, first, second):
    return order.index(first) < order.index(second)


def test_diamond_ordering_is_valid():
    edges = {"app": ["a", "b"], "a": ["base"], "b": ["base"], "base": []}
    order = resolve_order(edges)
    assert set(order) == {"app", "a", "b", "base"}
    assert len(order) == 4
    assert _precedes(order, "base", "a")
    assert _precedes(order, "base", "b")
    assert _precedes(order, "a", "app")
    assert _precedes(order, "b", "app")


def test_implicit_leaf_nodes_included():
    # "lib" is only ever mentioned as a dependency, never as a key.
    order = resolve_order({"app": ["lib"]})
    assert order == ["lib", "app"]


def test_self_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["a"]})


def test_three_node_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["b"], "b": ["c"], "c": ["a"]})


def test_cycle_detected_even_when_reachable_from_clean_root():
    with pytest.raises(CycleError):
        resolve_order({"root": ["a"], "a": ["b"], "b": ["a"]})


def test_disconnected_components():
    order = resolve_order({"x": ["y"], "p": ["q"], "y": [], "q": []})
    assert _precedes(order, "y", "x")
    assert _precedes(order, "q", "p")
    assert len(order) == 4


def test_empty_graph():
    assert resolve_order({}) == []
''',
        "fix": {
            "deps/resolve.py": '''\
from deps.graph import CycleError, Graph


def resolve_order(edges: dict[str, list[str]]) -> list[str]:
    """Return an install order: every dependency precedes its dependent."""
    graph = Graph(edges)
    order: list[str] = []
    done: set[str] = set()      # fully emitted
    on_stack: set[str] = set()  # currently being visited -> a revisit means a cycle

    def visit(node: str):
        if node in done:
            return
        if node in on_stack:
            raise CycleError(node)
        on_stack.add(node)
        for dep in graph.deps_of(node):
            visit(dep)
        on_stack.discard(node)
        done.add(node)
        order.append(node)

    for node in graph.nodes():
        visit(node)
    return order
''',
        },
    },
    # ------------------------------------------------------------------ routing
    {
        "id": "router-static-precedence",
        "problem": (
            "`router.match.Router` maps URL paths to handlers, supporting `{param}` segments. "
            "Matching is order-dependent: a dynamic route registered before a static one "
            "swallows requests the static route should win (`/users/{id}` shadows `/users/me`). "
            "Fix matching so a static segment always beats a dynamic one at the same position, "
            "regardless of registration order. Segment count must still match exactly."
        ),
        "files": {
            "router/__init__.py": "",
            "router/routes.py": '''\
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    pattern: str
    handler: str

    @property
    def segments(self) -> list[str]:
        return [s for s in self.pattern.strip("/").split("/") if s]


def is_dynamic(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def param_name(segment: str) -> str:
    return segment[1:-1]
''',
            "router/match.py": '''\
from router.routes import Route, is_dynamic, param_name


class Router:
    def __init__(self):
        self._routes: list[Route] = []

    def add(self, pattern: str, handler: str) -> None:
        self._routes.append(Route(pattern, handler))

    def match(self, path: str):
        """Return (handler, params) for `path`, or (None, {}) if nothing matches."""
        parts = [s for s in path.strip("/").split("/") if s]
        # BUG: the first route that matches wins, so precedence is registration
        # order rather than specificity - a dynamic route registered first
        # shadows a more specific static route.
        for route in self._routes:
            segs = route.segments
            if len(segs) != len(parts):
                continue
            params = {}
            for seg, part in zip(segs, parts):
                if is_dynamic(seg):
                    params[param_name(seg)] = part
                elif seg != part:
                    break
            else:
                return route.handler, params
        return None, {}
''',
        },
        "basic": '''\
from router.match import Router


def test_static_route():
    r = Router()
    r.add("/users/me", "me")
    assert r.match("/users/me") == ("me", {})


def test_static_beats_dynamic_registered_first():
    r = Router()
    r.add("/users/{id}", "by_id")
    r.add("/users/me", "me")
    assert r.match("/users/me") == ("me", {})
''',
        "oracle": '''\
from router.match import Router


def test_dynamic_still_matches_other_values():
    r = Router()
    r.add("/users/{id}", "by_id")
    r.add("/users/me", "me")
    assert r.match("/users/42") == ("by_id", {"id": "42"})


def test_specificity_at_later_segment():
    r = Router()
    r.add("/a/{x}/c", "dynamic")
    r.add("/a/b/c", "static")
    assert r.match("/a/b/c") == ("static", {})
    assert r.match("/a/z/c") == ("dynamic", {"x": "z"})


def test_leftmost_static_segment_wins():
    r = Router()
    r.add("/{a}/static", "left_dynamic")
    r.add("/static/{b}", "left_static")
    assert r.match("/static/static") == ("left_static", {"b": "static"})


def test_segment_count_must_match():
    r = Router()
    r.add("/users/{id}", "by_id")
    assert r.match("/users") == (None, {})
    assert r.match("/users/1/posts") == (None, {})


def test_multiple_params():
    r = Router()
    r.add("/u/{uid}/p/{pid}", "post")
    assert r.match("/u/7/p/9") == ("post", {"uid": "7", "pid": "9"})


def test_no_match_returns_none():
    r = Router()
    r.add("/a", "a")
    assert r.match("/b") == (None, {})


def test_trailing_slashes_ignored():
    r = Router()
    r.add("/users/me", "me")
    assert r.match("/users/me/") == ("me", {})
''',
        "fix": {
            "router/match.py": '''\
from router.routes import Route, is_dynamic, param_name


class Router:
    def __init__(self):
        self._routes: list[Route] = []

    def add(self, pattern: str, handler: str) -> None:
        self._routes.append(Route(pattern, handler))

    def match(self, path: str):
        """Return (handler, params) for `path`, or (None, {}) if nothing matches."""
        parts = [s for s in path.strip("/").split("/") if s]

        candidates = []
        for route in self._routes:
            segs = route.segments
            if len(segs) != len(parts):
                continue
            params = {}
            for seg, part in zip(segs, parts):
                if is_dynamic(seg):
                    params[param_name(seg)] = part
                elif seg != part:
                    break
            else:
                # Specificity: static segments outrank dynamic ones, compared
                # left to right, so the earliest static win decides.
                specificity = tuple(0 if is_dynamic(s) else 1 for s in segs)
                candidates.append((specificity, route.handler, params))

        if not candidates:
            return None, {}
        best = max(candidates, key=lambda c: c[0])
        return best[1], best[2]
''',
        },
    },
    # ------------------------------------------------------------- date ranges
    {
        "id": "daterange-merge-adjacent",
        "problem": (
            "`ranges.merge.merge_all` collapses a list of half-open integer ranges [start, end) "
            "into the smallest equivalent set. Two bugs: ranges that merely touch (10-20 and "
            "20-30) are left separate when they should combine into 10-30, and a range wholly "
            "contained inside another is emitted as a duplicate. Fix both. Output must be "
            "sorted by start, and empty ranges (start == end) must be dropped."
        ),
        "files": {
            "ranges/__init__.py": "",
            "ranges/interval.py": '''\
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Range:
    """A half-open interval [start, end)."""

    start: int
    end: int

    def is_empty(self) -> bool:
        return self.start >= self.end

    def overlaps(self, other: "Range") -> bool:
        # BUG: half-open ranges that touch at a boundary (end == other.start)
        # are contiguous and must be merged, but strict inequality rejects them.
        return self.start < other.end and other.start < self.end
''',
            "ranges/merge.py": '''\
from ranges.interval import Range


def merge_all(ranges: list[Range]) -> list[Range]:
    """Collapse overlapping or adjacent ranges into a minimal sorted list."""
    items = sorted(r for r in ranges if not r.is_empty())
    if not items:
        return []

    out = [items[0]]
    for current in items[1:]:
        last = out[-1]
        if last.overlaps(current):
            # BUG: the merged end takes the incoming range's end unconditionally,
            # so a range fully contained in `last` shrinks it.
            out[-1] = Range(last.start, current.end)
        else:
            out.append(current)
    return out
''',
        },
        "basic": '''\
from ranges.interval import Range
from ranges.merge import merge_all


def test_overlapping_merge():
    assert merge_all([Range(1, 5), Range(3, 8)]) == [Range(1, 8)]


def test_touching_ranges_merge():
    assert merge_all([Range(10, 20), Range(20, 30)]) == [Range(10, 30)]
''',
        "oracle": '''\
from ranges.interval import Range
from ranges.merge import merge_all


def test_contained_range_does_not_shrink_parent():
    assert merge_all([Range(1, 100), Range(10, 20)]) == [Range(1, 100)]


def test_identical_ranges_collapse():
    assert merge_all([Range(1, 5), Range(1, 5)]) == [Range(1, 5)]


def test_disjoint_preserved_and_sorted():
    assert merge_all([Range(40, 50), Range(1, 5)]) == [Range(1, 5), Range(40, 50)]


def test_gap_of_one_not_merged():
    assert merge_all([Range(1, 5), Range(6, 9)]) == [Range(1, 5), Range(6, 9)]


def test_empty_ranges_dropped():
    assert merge_all([Range(3, 3), Range(1, 2)]) == [Range(1, 2)]
    assert merge_all([Range(5, 5)]) == []


def test_chain_merges_transitively():
    got = merge_all([Range(1, 3), Range(3, 5), Range(5, 7), Range(9, 11)])
    assert got == [Range(1, 7), Range(9, 11)]


def test_empty_input():
    assert merge_all([]) == []
''',
        "fix": {
            "ranges/interval.py": '''\
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Range:
    """A half-open interval [start, end)."""

    start: int
    end: int

    def is_empty(self) -> bool:
        return self.start >= self.end

    def overlaps(self, other: "Range") -> bool:
        # Half-open ranges that touch at a boundary are contiguous, so <= is
        # the correct comparison for mergeability.
        return self.start <= other.end and other.start <= self.end
''',
            "ranges/merge.py": '''\
from ranges.interval import Range


def merge_all(ranges: list[Range]) -> list[Range]:
    """Collapse overlapping or adjacent ranges into a minimal sorted list."""
    items = sorted(r for r in ranges if not r.is_empty())
    if not items:
        return []

    out = [items[0]]
    for current in items[1:]:
        last = out[-1]
        if last.overlaps(current):
            # Take the furthest end so a contained range never shrinks its parent.
            out[-1] = Range(last.start, max(last.end, current.end))
        else:
            out.append(current)
    return out
''',
        },
    },
    # -------------------------------------------------------------------- authz
    {
        "id": "authz-deny-precedence",
        "problem": (
            "`authz.check.can` decides whether a role may perform an action, with roles "
            "inheriting permissions from parents defined in `authz.roles`. An explicit deny on "
            "a child role is currently overridden by an inherited allow, when deny must always "
            "win. Inheritance also fails to terminate on a role cycle. Fix both: an explicit "
            "deny anywhere in the inheritance chain beats any allow, and a cycle must not hang."
        ),
        "files": {
            "authz/__init__.py": "",
            "authz/roles.py": '''\
ALLOW = "allow"
DENY = "deny"


class RoleGraph:
    def __init__(self, roles: dict):
        """roles: name -> {"parents": [...], "rules": {action: ALLOW|DENY}}"""
        self.roles = roles

    def parents_of(self, role: str) -> list:
        return self.roles.get(role, {}).get("parents", [])

    def rule_for(self, role: str, action: str):
        return self.roles.get(role, {}).get("rules", {}).get(action)
''',
            "authz/check.py": '''\
from authz.roles import ALLOW, DENY, RoleGraph


def can(roles: dict, role: str, action: str) -> bool:
    """True if `role` may perform `action`."""
    graph = RoleGraph(roles)

    def resolve(name: str):
        # BUG: the first rule found wins and the walk returns immediately, so an
        # inherited ALLOW can be returned before a DENY deeper in the chain is
        # ever considered. BUG: nothing tracks visited roles, so a parent cycle
        # recurses forever.
        rule = graph.rule_for(name, action)
        if rule is not None:
            return rule
        for parent in graph.parents_of(name):
            found = resolve(parent)
            if found is not None:
                return found
        return None

    return resolve(role) == ALLOW
''',
        },
        "basic": '''\
from authz.check import can
from authz.roles import ALLOW, DENY


def test_direct_allow():
    roles = {"admin": {"parents": [], "rules": {"delete": ALLOW}}}
    assert can(roles, "admin", "delete") is True


def test_deny_further_up_the_chain_still_wins():
    roles = {
        "base": {"parents": [], "rules": {"write": DENY}},
        "mid": {"parents": ["base"], "rules": {"write": ALLOW}},
        "leaf": {"parents": ["mid"], "rules": {}},
    }
    assert can(roles, "leaf", "write") is False
''',
        "oracle": '''\
from authz.check import can
from authz.roles import ALLOW, DENY


def test_deny_deeper_in_chain_beats_nearer_allow():
    roles = {
        "base": {"parents": [], "rules": {"write": DENY}},
        "mid": {"parents": ["base"], "rules": {"write": ALLOW}},
        "leaf": {"parents": ["mid"], "rules": {}},
    }
    assert can(roles, "leaf", "write") is False


def test_deny_in_any_branch_wins():
    roles = {
        "a": {"parents": [], "rules": {"read": ALLOW}},
        "b": {"parents": [], "rules": {"read": DENY}},
        "leaf": {"parents": ["a", "b"], "rules": {}},
    }
    assert can(roles, "leaf", "read") is False


def test_inherited_allow_without_deny():
    roles = {
        "admin": {"parents": [], "rules": {"delete": ALLOW}},
        "staff": {"parents": ["admin"], "rules": {}},
    }
    assert can(roles, "staff", "delete") is True


def test_no_rule_anywhere_is_denied_by_default():
    roles = {"guest": {"parents": [], "rules": {}}}
    assert can(roles, "guest", "delete") is False


def test_unknown_role_denied():
    assert can({}, "ghost", "read") is False


def test_role_cycle_terminates():
    roles = {
        "a": {"parents": ["b"], "rules": {}},
        "b": {"parents": ["a"], "rules": {}},
    }
    assert can(roles, "a", "read") is False


def test_cycle_with_allow_still_resolves():
    roles = {
        "a": {"parents": ["b"], "rules": {}},
        "b": {"parents": ["a"], "rules": {"read": ALLOW}},
    }
    assert can(roles, "a", "read") is True
''',
        "fix": {
            "authz/check.py": '''\
from authz.roles import ALLOW, DENY, RoleGraph


def can(roles: dict, role: str, action: str) -> bool:
    """True if `role` may perform `action`."""
    graph = RoleGraph(roles)
    seen: set = set()
    found_allow = False

    def walk(name: str) -> bool:
        """Visit the chain, returning True as soon as a DENY is seen."""
        nonlocal found_allow
        if name in seen:
            return False
        seen.add(name)

        rule = graph.rule_for(name, action)
        if rule == DENY:
            return True
        if rule == ALLOW:
            found_allow = True

        # Keep walking even after an ALLOW: a deny further up must still win.
        for parent in graph.parents_of(name):
            if walk(parent):
                return True
        return False

    denied = walk(role)
    return found_allow and not denied
''',
        },
    },
    # ----------------------------------------------------------------- batching
    {
        "id": "batch-buffer-flush",
        "problem": (
            "`batch.buffer.Batcher` accumulates items and flushes them to a sink when the batch "
            "reaches `max_size` or `max_age` seconds have passed since the batch's first item. "
            "Two bugs: `close()` discards a partially filled batch instead of flushing it, and "
            "the age check measures from the most recent item rather than the first, so a "
            "steady trickle of items never ages out. Fix both; flushes must preserve order and "
            "an empty batch must never reach the sink."
        ),
        "files": {
            "batch/__init__.py": "",
            "batch/clock.py": '''\
class ManualClock:
    def __init__(self, now: float = 0.0):
        self._now = now

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
''',
            "batch/buffer.py": '''\
from batch.clock import ManualClock


class Batcher:
    def __init__(self, sink, max_size: int = 3, max_age: float = 5.0, clock=None):
        self.sink = sink
        self.max_size = max_size
        self.max_age = max_age
        self.clock = clock or ManualClock()
        self._items: list = []
        self._last_add = self.clock.time()

    def add(self, item) -> None:
        self._items.append(item)
        # BUG: the age reference resets on every add, so a slow but steady
        # stream never reaches max_age and the batch is never time-flushed.
        self._last_add = self.clock.time()
        if len(self._items) >= self.max_size:
            self.flush()

    def tick(self) -> None:
        """Give the batcher a chance to flush on age alone."""
        if self._items and self.clock.time() - self._last_add >= self.max_age:
            self.flush()

    def flush(self) -> None:
        if not self._items:
            return
        self.sink(list(self._items))
        self._items.clear()

    def close(self) -> None:
        # BUG: pending items are dropped on close instead of being flushed.
        self._items.clear()
''',
        },
        "basic": '''\
from batch.buffer import Batcher
from batch.clock import ManualClock


def test_flush_on_size():
    out = []
    b = Batcher(out.append, max_size=2, clock=ManualClock())
    b.add(1)
    b.add(2)
    assert out == [[1, 2]]


def test_close_flushes_partial_batch():
    out = []
    b = Batcher(out.append, max_size=5, clock=ManualClock())
    b.add(1)
    b.close()
    assert out == [[1]]
''',
        "oracle": '''\
from batch.buffer import Batcher
from batch.clock import ManualClock


def test_age_measured_from_first_item():
    out = []
    clock = ManualClock()
    b = Batcher(out.append, max_size=10, max_age=5, clock=clock)
    b.add("a")
    clock.advance(3)
    b.add("b")      # a steady trickle must not reset the batch's age
    clock.advance(3)
    b.tick()
    assert out == [["a", "b"]]


def test_tick_before_max_age_does_not_flush():
    out = []
    clock = ManualClock()
    b = Batcher(out.append, max_size=10, max_age=5, clock=clock)
    b.add("a")
    clock.advance(4)
    b.tick()
    assert out == []


def test_close_on_empty_buffer_emits_nothing():
    out = []
    b = Batcher(out.append, max_size=3, clock=ManualClock())
    b.close()
    assert out == []


def test_order_preserved_across_batches():
    out = []
    b = Batcher(out.append, max_size=2, clock=ManualClock())
    for i in range(5):
        b.add(i)
    b.close()
    assert out == [[0, 1], [2, 3], [4]]


def test_age_resets_after_flush():
    out = []
    clock = ManualClock()
    b = Batcher(out.append, max_size=10, max_age=5, clock=clock)
    b.add("a")
    clock.advance(6)
    b.tick()
    assert out == [["a"]]
    b.add("b")
    clock.advance(1)
    b.tick()
    assert out == [["a"]]      # the new batch is only 1s old


def test_tick_on_empty_buffer_is_safe():
    out = []
    clock = ManualClock()
    b = Batcher(out.append, max_size=3, max_age=1, clock=clock)
    clock.advance(100)
    b.tick()
    assert out == []
''',
        "fix": {
            "batch/buffer.py": '''\
from batch.clock import ManualClock


class Batcher:
    def __init__(self, sink, max_size: int = 3, max_age: float = 5.0, clock=None):
        self.sink = sink
        self.max_size = max_size
        self.max_age = max_age
        self.clock = clock or ManualClock()
        self._items: list = []
        # Timestamp of the batch's *first* item, so age reflects how long the
        # oldest item has waited rather than how recently one arrived.
        self._batch_started = None

    def add(self, item) -> None:
        if not self._items:
            self._batch_started = self.clock.time()
        self._items.append(item)
        if len(self._items) >= self.max_size:
            self.flush()

    def tick(self) -> None:
        """Give the batcher a chance to flush on age alone."""
        if self._items and self.clock.time() - self._batch_started >= self.max_age:
            self.flush()

    def flush(self) -> None:
        if not self._items:
            return
        self.sink(list(self._items))
        self._items.clear()
        self._batch_started = None

    def close(self) -> None:
        self.flush()
''',
        },
    },
    # --------------------------------------------------------------- validation
    {
        "id": "schema-validate-nested",
        "problem": (
            "`schema.validate.validate` checks a dict against a small schema spec built from "
            "`schema.types`. Nested object schemas are not descended into at all, so errors "
            "inside them go unreported, and a field explicitly marked optional is still "
            "reported as missing when absent. Fix both. Error paths must be dotted "
            "(`user.address.city`) and the returned list must be empty when the value is valid."
        ),
        "files": {
            "schema/__init__.py": "",
            "schema/types.py": '''\
from dataclasses import dataclass, field


@dataclass
class Field:
    kind: str                       # "str" | "int" | "object"
    required: bool = True
    fields: dict = field(default_factory=dict)   # for kind == "object"


PYTHON_TYPES = {"str": str, "int": int, "object": dict}
''',
            "schema/validate.py": '''\
from schema.types import PYTHON_TYPES, Field


def validate(value: dict, schema: dict[str, Field], path: str = "") -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    for name, spec in schema.items():
        where = f"{path}.{name}" if path else name

        if name not in value:
            # BUG: absence is reported regardless of whether the field is required.
            errors.append(f"{where}: missing required field")
            continue

        actual = value[name]
        expected = PYTHON_TYPES[spec.kind]
        if not isinstance(actual, expected):
            errors.append(f"{where}: expected {spec.kind}, got {type(actual).__name__}")
            continue

        # BUG: nested object schemas are never validated, so errors inside a
        # nested dict are silently ignored.
    return errors
''',
        },
        "basic": '''\
from schema.types import Field
from schema.validate import validate


def test_missing_required_reported():
    errors = validate({}, {"name": Field("str")})
    assert errors == ["name: missing required field"]


def test_optional_field_may_be_absent():
    assert validate({}, {"nick": Field("str", required=False)}) == []
''',
        "oracle": '''\
from schema.types import Field
from schema.validate import validate


def test_nested_errors_are_reported_with_dotted_path():
    schema = {
        "user": Field("object", fields={
            "address": Field("object", fields={"city": Field("str")}),
        }),
    }
    errors = validate({"user": {"address": {}}}, schema)
    assert errors == ["user.address.city: missing required field"]


def test_nested_type_error():
    schema = {"user": Field("object", fields={"age": Field("int")})}
    errors = validate({"user": {"age": "old"}}, schema)
    assert errors == ["user.age: expected int, got str"]


def test_valid_nested_value_has_no_errors():
    schema = {"user": Field("object", fields={"name": Field("str")})}
    assert validate({"user": {"name": "ada"}}, schema) == []


def test_optional_nested_object_absent_is_fine():
    schema = {"meta": Field("object", required=False, fields={"k": Field("str")})}
    assert validate({}, schema) == []


def test_optional_field_present_is_still_type_checked():
    assert validate({"nick": 5}, {"nick": Field("str", required=False)}) == [
        "nick: expected str, got int"
    ]


def test_top_level_type_error_short_circuits_nesting():
    schema = {"user": Field("object", fields={"name": Field("str")})}
    assert validate({"user": "nope"}, schema) == ["user: expected object, got str"]


def test_multiple_errors_collected():
    schema = {"a": Field("str"), "b": Field("int")}
    errors = validate({}, schema)
    assert len(errors) == 2
''',
        "fix": {
            "schema/validate.py": '''\
from schema.types import PYTHON_TYPES, Field


def validate(value: dict, schema: dict[str, Field], path: str = "") -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    for name, spec in schema.items():
        where = f"{path}.{name}" if path else name

        if name not in value:
            if spec.required:
                errors.append(f"{where}: missing required field")
            continue

        actual = value[name]
        expected = PYTHON_TYPES[spec.kind]
        if not isinstance(actual, expected):
            errors.append(f"{where}: expected {spec.kind}, got {type(actual).__name__}")
            continue

        if spec.kind == "object" and spec.fields:
            errors.extend(validate(actual, spec.fields, where))
    return errors
''',
        },
    },
    # ----------------------------------------------------------------- wrapping
    {
        "id": "text-wrap-long-words",
        "problem": (
            "`wrapping.wrap.wrap_text` breaks a string into lines of at most `width` characters. "
            "A single word longer than `width` currently produces a line that exceeds the limit "
            "instead of being hard-split across lines, and lines come back with trailing spaces. "
            "Fix both. Words are separated by single spaces in the output, no line may exceed "
            "`width`, and an empty input yields an empty list."
        ),
        "files": {
            "wrapping/__init__.py": "",
            "wrapping/wrap.py": '''\
def wrap_text(text: str, width: int) -> list[str]:
    """Wrap `text` into lines no longer than `width` characters."""
    if width <= 0:
        raise ValueError("width must be positive")

    lines: list[str] = []
    current = ""
    for word in text.split():
        # BUG: a word longer than `width` is appended whole, producing an
        # over-long line instead of being hard-split. BUG: words are joined by
        # appending a trailing space, which is never stripped.
        if len(current) + len(word) <= width:
            current += word + " "
        else:
            lines.append(current)
            current = word + " "
    if current:
        lines.append(current)
    return lines
''',
        },
        "basic": '''\
from wrapping.wrap import wrap_text


def test_simple_wrap():
    assert wrap_text("aaa bbb ccc", 7) == ["aaa bbb", "ccc"]


def test_long_word_is_split():
    assert wrap_text("abcdefghij", 4) == ["abcd", "efgh", "ij"]
''',
        "oracle": '''\
import pytest

from wrapping.wrap import wrap_text


def test_no_trailing_whitespace():
    for line in wrap_text("aaa bbb ccc ddd", 7):
        assert line == line.rstrip()


def test_no_line_exceeds_width():
    text = "short longerword tiny supercalifragilistic x"
    for line in wrap_text(text, 8):
        assert len(line) <= 8


def test_long_word_mixed_with_short_ones():
    assert wrap_text("hi abcdefghij yo", 4) == ["hi", "abcd", "efgh", "ij", "yo"]


def test_exact_width_word_fits_alone():
    assert wrap_text("abcd efg", 4) == ["abcd", "efg"]


def test_empty_input():
    assert wrap_text("", 5) == []
    assert wrap_text("   ", 5) == []


def test_single_word_shorter_than_width():
    assert wrap_text("hi", 10) == ["hi"]


def test_width_of_one():
    assert wrap_text("ab c", 1) == ["a", "b", "c"]


def test_invalid_width():
    with pytest.raises(ValueError):
        wrap_text("hi", 0)
''',
        "fix": {
            "wrapping/wrap.py": '''\
def wrap_text(text: str, width: int) -> list[str]:
    """Wrap `text` into lines no longer than `width` characters."""
    if width <= 0:
        raise ValueError("width must be positive")

    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            lines.append(" ".join(current))
            current = []
            current_len = 0

    for word in text.split():
        # Hard-split any word that cannot fit on a line of its own.
        while len(word) > width:
            flush()
            lines.append(word[:width])
            word = word[width:]

        # +1 for the space that would join this word to the current line.
        needed = len(word) if not current else current_len + 1 + len(word)
        if needed > width:
            flush()
            needed = len(word)
        current.append(word)
        current_len = needed

    flush()
    return lines
''',
        },
    },
    # -------------------------------------------------------------------- money
    {
        "id": "money-allocate-remainder",
        "problem": (
            "`money.allocate.allocate` splits an integer amount of cents across weighted "
            "recipients. Rounding loses or invents cents: the allocated parts do not always sum "
            "back to the original amount. Fix it so the parts always sum exactly to `amount`, "
            "distributing any remainder one cent at a time to the recipients with the largest "
            "fractional part (ties broken by original order). Negative amounts are not supported "
            "and must raise ValueError."
        ),
        "files": {
            "money/__init__.py": "",
            "money/allocate.py": '''\
def allocate(amount: int, weights: list[float]) -> list[int]:
    """Split `amount` cents across `weights`, returning whole cents."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if not weights or sum(weights) <= 0:
        raise ValueError("weights must be non-empty and sum to a positive value")

    total = sum(weights)
    # BUG: each part is rounded independently, so the parts can sum to more or
    # less than `amount` - the remainder is never reconciled.
    return [round(amount * w / total) for w in weights]
''',
        },
        "basic": '''\
from money.allocate import allocate


def test_even_split():
    assert allocate(100, [1, 1]) == [50, 50]


def test_parts_sum_to_amount():
    parts = allocate(100, [1, 1, 1])
    assert sum(parts) == 100
''',
        "oracle": '''\
import pytest

from money.allocate import allocate


def test_thirds_distribute_remainder_to_largest_fraction():
    # 100/3 = 33.33 each; the two leftover cents go to the first two.
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]


def test_sum_preserved_across_many_shapes():
    for amount in (0, 1, 7, 99, 100, 1234):
        for weights in ([1, 1, 1], [2, 1], [1, 1, 1, 1, 1, 1, 1], [5, 3, 2]):
            assert sum(allocate(amount, weights)) == amount


def test_weighted_split():
    assert allocate(100, [3, 1]) == [75, 25]


def test_zero_amount():
    assert allocate(0, [1, 2, 3]) == [0, 0, 0]


def test_single_recipient_gets_everything():
    assert allocate(97, [1]) == [97]


def test_zero_weight_gets_nothing():
    parts = allocate(100, [1, 0, 1])
    assert parts[1] == 0
    assert sum(parts) == 100


def test_ties_broken_by_original_order():
    assert allocate(10, [1, 1, 1]) == [4, 3, 3]


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        allocate(-1, [1])


def test_empty_weights_rejected():
    with pytest.raises(ValueError):
        allocate(10, [])
''',
        "fix": {
            "money/allocate.py": '''\
def allocate(amount: int, weights: list[float]) -> list[int]:
    """Split `amount` cents across `weights`, returning whole cents."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if not weights or sum(weights) <= 0:
        raise ValueError("weights must be non-empty and sum to a positive value")

    total = sum(weights)
    exact = [amount * w / total for w in weights]
    parts = [int(x) for x in exact]           # floor, so the sum never overshoots

    # Hand the shortfall out one cent at a time, largest fractional part first.
    remainder = amount - sum(parts)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(exact[i] - parts[i]), i),
    )
    for i in order[:remainder]:
        parts[i] += 1
    return parts
''',
        },
    },
]
