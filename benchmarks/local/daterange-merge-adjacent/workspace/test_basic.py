from ranges.interval import Range
from ranges.merge import merge_all


def test_overlapping_merge():
    assert merge_all([Range(1, 5), Range(3, 8)]) == [Range(1, 8)]


def test_touching_ranges_merge():
    assert merge_all([Range(10, 20), Range(20, 30)]) == [Range(10, 30)]
