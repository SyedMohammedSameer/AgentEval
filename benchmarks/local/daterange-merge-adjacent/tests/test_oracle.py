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
