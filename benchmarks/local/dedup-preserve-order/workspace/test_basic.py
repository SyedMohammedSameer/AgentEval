from seqtools import dedup


def test_basic():
    assert dedup([1, 1, 2, 3]) == [1, 2, 3]
