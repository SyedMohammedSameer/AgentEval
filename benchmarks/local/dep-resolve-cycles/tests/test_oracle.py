import pytest

from deps.graph import CycleError
from deps.resolve import resolve_order


def _precedes(order, first, second):
    return order.index(first) < order.index(second)


def test_diamond_ordering_is_valid():
    edges = {"app": ["a", "b"], "a": ["base"], "b": ["base"], "base": []}
    order = resolve_order(edges)
    assert set(order) == {"app", "a", "b", "base"}
    assert len(order) == 4
    assert _precedes(order, "base", "a")
    assert _precedes(order, "base", "b")
    assert _precedes(order, "a", "app")
    assert _precedes(order, "b", "app")


def test_implicit_leaf_nodes_included():
    # "lib" is only ever mentioned as a dependency, never as a key.
    order = resolve_order({"app": ["lib"]})
    assert order == ["lib", "app"]


def test_self_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["a"]})


def test_three_node_cycle_raises():
    with pytest.raises(CycleError):
        resolve_order({"a": ["b"], "b": ["c"], "c": ["a"]})


def test_cycle_detected_even_when_reachable_from_clean_root():
    with pytest.raises(CycleError):
        resolve_order({"root": ["a"], "a": ["b"], "b": ["a"]})


def test_disconnected_components():
    order = resolve_order({"x": ["y"], "p": ["q"], "y": [], "q": []})
    assert _precedes(order, "y", "x")
    assert _precedes(order, "q", "p")
    assert len(order) == 4


def test_empty_graph():
    assert resolve_order({}) == []
