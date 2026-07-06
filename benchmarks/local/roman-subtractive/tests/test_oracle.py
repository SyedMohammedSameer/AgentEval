from roman import to_roman


def test_nine():
    assert to_roman(9) == "IX"


def test_forty():
    assert to_roman(40) == "XL"


def test_composite():
    assert to_roman(1994) == "MCMXCIV"


def test_year():
    assert to_roman(2023) == "MMXXIII"
