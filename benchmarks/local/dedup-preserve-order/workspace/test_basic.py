from seqtools import dedup


def test_basic():
    assert dedup([1, 1, 2, 3]) == [1, 2, 3]


def test_order_of_first_appearance():
    assert dedup([3, 1, 3, 2]) == [3, 1, 2]
