from patcher.apply import apply_hunks
from patcher.hunk import Hunk

TEXT = "a\nb\nc\nd\ne"


def test_single_hunk():
    assert apply_hunks(TEXT, [Hunk(2, 1, ("B",))]) == "a\nB\nc\nd\ne"


def test_second_hunk_after_an_insertion():
    hunks = [Hunk(1, 1, ("A1", "A2")), Hunk(4, 1, ("D",))]
    assert apply_hunks(TEXT, hunks) == "A1\nA2\nb\nc\nD\ne"
