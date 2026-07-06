from cipher import encode


def test_wrap_lower():
    assert encode("xyz", 3) == "abc"


def test_wrap_upper():
    assert encode("XYZ", 3) == "ABC"


def test_shift_over_26():
    assert encode("abc", 27) == "bcd"


def test_punct_passthrough():
    assert encode("a-b", 1) == "b-c"
