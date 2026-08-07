import pytest

from deps.graph import CycleError
from deps.resolve import resolve_order


def test_linear_chain():
    assert resolve_order({"app": ["lib"], "lib": []}) == ["lib", "app"]


def test_diamond_has_no_duplicates():
    order = resolve_order({"app": ["a", "b"], "a": ["base"], "b": ["base"], "base": []})
    assert order.count("base") == 1
    assert len(order) == len(set(order))


def test_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["b"], "b": ["a"]})
