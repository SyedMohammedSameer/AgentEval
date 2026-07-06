from nest import flatten


def test_deep():
    assert flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4]


def test_lists_of_lists():
    assert flatten([[1], [2], [3]]) == [1, 2, 3]


def test_empty():
    assert flatten([]) == []
