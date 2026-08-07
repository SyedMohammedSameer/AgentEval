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
