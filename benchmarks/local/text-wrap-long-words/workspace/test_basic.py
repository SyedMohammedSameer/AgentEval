from wrapping.wrap import wrap_text


def test_simple_wrap():
    assert wrap_text("aaa bbb ccc", 7) == ["aaa bbb", "ccc"]


def test_long_word_is_split():
    assert wrap_text("abcdefghij", 4) == ["abcd", "efgh", "ij"]
