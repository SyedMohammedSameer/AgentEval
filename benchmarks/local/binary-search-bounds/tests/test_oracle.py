from bsearch import search


def test_empty():
    assert search([], 1) == -1


def test_first():
    assert search([1, 2, 3, 4, 5], 1) == 0


def test_last():
    assert search([1, 2, 3, 4, 5], 5) == 4


def test_absent_middle():
    assert search([1, 3, 5, 7], 4) == -1
