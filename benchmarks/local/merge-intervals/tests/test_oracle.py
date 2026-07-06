from intervals import merge


def test_touching():
    assert merge([[1, 2], [2, 3]]) == [[1, 3]]


def test_disjoint():
    assert merge([[1, 4], [5, 6]]) == [[1, 4], [5, 6]]


def test_nested():
    assert merge([[1, 4], [2, 3]]) == [[1, 4]]
