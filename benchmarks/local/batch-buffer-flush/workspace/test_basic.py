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
