from roman import to_roman


def test_simple():
    assert to_roman(3) == "III"


def test_four():
    assert to_roman(4) == "IV"
