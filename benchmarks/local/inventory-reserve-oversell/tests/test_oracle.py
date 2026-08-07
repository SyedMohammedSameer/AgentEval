import pytest

from inventory.ledger import InsufficientStock
from inventory.store import Store


def test_over_release_cannot_inflate_availability():
    s = Store({"widget": 5})
    s.reserve("widget", 2)
    s.release("widget", 10)
    assert s.available("widget") == 5


def test_release_returns_units_for_reuse():
    s = Store({"widget": 5})
    s.reserve("widget", 3)
    s.release("widget", 3)
    assert s.available("widget") == 5
    s.reserve("widget", 5)
    assert s.available("widget") == 0


def test_reserving_exactly_what_is_available_succeeds():
    s = Store({"w": 4})
    s.reserve("w", 4)
    assert s.available("w") == 0


def test_commit_removes_units_from_on_hand():
    s = Store({"w": 5})
    s.reserve("w", 2)
    s.commit("w", 2)
    assert s.available("w") == 3


def test_availability_never_exceeds_on_hand():
    s = Store({"w": 3})
    s.reserve("w", 3)
    for _ in range(3):
        s.release("w", 1)
    s.release("w", 5)
    assert s.available("w") == 3


def test_unknown_sku():
    s = Store({"w": 1})
    assert s.available("nope") == 0
    with pytest.raises(InsufficientStock):
        s.reserve("nope", 1)


def test_non_positive_quantity_rejected():
    s = Store({"w": 1})
    with pytest.raises(ValueError):
        s.reserve("w", 0)
