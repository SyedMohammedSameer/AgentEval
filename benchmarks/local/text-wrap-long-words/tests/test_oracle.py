import pytest

from wrapping.wrap import wrap_text


def test_no_trailing_whitespace():
    for line in wrap_text("aaa bbb ccc ddd", 7):
        assert line == line.rstrip()


def test_no_line_exceeds_width():
    text = "short longerword tiny supercalifragilistic x"
    for line in wrap_text(text, 8):
        assert len(line) <= 8


def test_long_word_mixed_with_short_ones():
    assert wrap_text("hi abcdefghij yo", 4) == ["hi", "abcd", "efgh", "ij", "yo"]


def test_exact_width_word_fits_alone():
    assert wrap_text("abcd efg", 4) == ["abcd", "efg"]


def test_empty_input():
    assert wrap_text("", 5) == []
    assert wrap_text("   ", 5) == []


def test_single_word_shorter_than_width():
    assert wrap_text("hi", 10) == ["hi"]


def test_width_of_one():
    assert wrap_text("ab c", 1) == ["a", "b", "c"]


def test_invalid_width():
    with pytest.raises(ValueError):
        wrap_text("hi", 0)
