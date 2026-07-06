from cipher import encode


def test_simple():
    assert encode("abc", 1) == "bcd"
