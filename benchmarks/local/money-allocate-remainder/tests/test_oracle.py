import pytest

from money.allocate import allocate


def test_thirds_distribute_remainder_to_largest_fraction():
    # 100/3 = 33.33 each; the two leftover cents go to the first two.
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]


def test_sum_preserved_across_many_shapes():
    for amount in (0, 1, 7, 99, 100, 1234):
        for weights in ([1, 1, 1], [2, 1], [1, 1, 1, 1, 1, 1, 1], [5, 3, 2]):
            assert sum(allocate(amount, weights)) == amount


def test_weighted_split():
    assert allocate(100, [3, 1]) == [75, 25]


def test_zero_amount():
    assert allocate(0, [1, 2, 3]) == [0, 0, 0]


def test_single_recipient_gets_everything():
    assert allocate(97, [1]) == [97]


def test_zero_weight_gets_nothing():
    parts = allocate(100, [1, 0, 1])
    assert parts[1] == 0
    assert sum(parts) == 100


def test_ties_broken_by_original_order():
    assert allocate(10, [1, 1, 1]) == [4, 3, 3]


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        allocate(-1, [1])


def test_empty_weights_rejected():
    with pytest.raises(ValueError):
        allocate(10, [])
