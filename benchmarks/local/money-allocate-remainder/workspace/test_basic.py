from money.allocate import allocate


def test_even_split():
    assert allocate(100, [1, 1]) == [50, 50]


def test_parts_sum_to_amount():
    parts = allocate(100, [1, 1, 1])
    assert sum(parts) == 100
