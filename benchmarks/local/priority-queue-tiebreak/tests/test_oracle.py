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
