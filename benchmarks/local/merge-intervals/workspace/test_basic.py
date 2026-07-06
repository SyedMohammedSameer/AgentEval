from intervals import merge


def test_overlap():
    assert merge([[1, 3], [2, 6]]) == [[1, 6]]
