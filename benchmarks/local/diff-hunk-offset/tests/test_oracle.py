import pytest

from patcher.apply import apply_hunks
from patcher.hunk import Hunk, PatchError

TEXT = "a\nb\nc\nd\ne"


def test_deletion_shifts_later_hunks():
    hunks = [Hunk(1, 3, ("X",)), Hunk(5, 1, ("E",))]
    assert apply_hunks(TEXT, hunks) == "X\nd\nE"


def test_three_hunks_growing_and_shrinking():
    hunks = [Hunk(1, 1, ("A", "A2")), Hunk(3, 1, ()), Hunk(5, 1, ("E",))]
    assert apply_hunks(TEXT, hunks) == "A\nA2\nb\nd\nE"


def test_input_order_does_not_matter():
    hunks = [Hunk(4, 1, ("D",)), Hunk(1, 1, ("A1", "A2"))]
    assert apply_hunks(TEXT, hunks) == "A1\nA2\nb\nc\nD\ne"


def test_pure_deletion():
    assert apply_hunks(TEXT, [Hunk(2, 2, ())]) == "a\nd\ne"


def test_insertion_at_the_end():
    assert apply_hunks(TEXT, [Hunk(5, 1, ("e", "f"))]) == "a\nb\nc\nd\ne\nf"


def test_out_of_range_hunk_raises():
    with pytest.raises(PatchError):
        apply_hunks(TEXT, [Hunk(10, 1, ("x",))])


def test_no_hunks_is_identity():
    assert apply_hunks(TEXT, []) == TEXT
