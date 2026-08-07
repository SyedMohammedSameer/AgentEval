import pytest

from inventory.ledger import InsufficientStock
from inventory.store import Store


def test_reserve_reduces_available():
    s = Store({"widget": 10})
    s.reserve("widget", 4)
    assert s.available("widget") == 6


def test_cannot_oversell_across_two_reservations():
    s = Store({"widget": 10})
    s.reserve("widget", 8)
    with pytest.raises(InsufficientStock):
        s.reserve("widget", 5)
