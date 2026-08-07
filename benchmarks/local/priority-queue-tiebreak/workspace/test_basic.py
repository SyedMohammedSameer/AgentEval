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
