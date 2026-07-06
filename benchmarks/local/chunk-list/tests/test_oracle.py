from chunk import chunk


def test_remainder():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_exact():
    assert chunk([1, 2, 3], 3) == [[1, 2, 3]]


def test_bigger_than_list():
    assert chunk([1, 2], 5) == [[1, 2]]
