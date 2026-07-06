from chunk import chunk


def test_even():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
