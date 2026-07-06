from rle import encode


def test_multi():
    assert encode("aaabbc") == "a3b2c1"


def test_single():
    assert encode("a") == "a1"


def test_empty():
    assert encode("") == ""
