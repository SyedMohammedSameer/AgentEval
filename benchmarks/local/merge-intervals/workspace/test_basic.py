from intervals import merge


def test_overlap():
    assert merge([[1, 3], [2, 6]]) == [[1, 6]]


def test_touching_intervals_merge():
    assert merge([[1, 2], [2, 3]]) == [[1, 3]]
