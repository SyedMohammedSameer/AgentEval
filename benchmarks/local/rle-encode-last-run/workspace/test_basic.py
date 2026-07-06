from rle import encode


def test_basic():
    assert encode("aaab") == "a3b1"
