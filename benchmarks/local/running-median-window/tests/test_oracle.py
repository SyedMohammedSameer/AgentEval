from stats import moving_average


def test_window_three():
    assert moving_average([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]


def test_full_window():
    assert moving_average([2, 4, 6], 3) == [4.0]


def test_k_one():
    assert moving_average([5, 6, 7], 1) == [5.0, 6.0, 7.0]
