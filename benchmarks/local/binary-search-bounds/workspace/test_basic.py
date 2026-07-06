from bsearch import search


def test_found():
    assert search([1, 2, 3], 2) == 1


def test_missing_high():
    assert search([1, 2, 3], 9) == -1
