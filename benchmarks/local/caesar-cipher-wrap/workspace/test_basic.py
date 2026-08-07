from cipher import encode


def test_simple():
    assert encode("abc", 1) == "bcd"


def test_wraps_past_z():
    assert encode("z", 1) == "a"
