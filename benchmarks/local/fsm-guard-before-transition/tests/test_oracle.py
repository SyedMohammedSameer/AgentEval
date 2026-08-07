import pytest

from fsm.machine import Machine
from fsm.transitions import Transition, UnknownTransition


def _machine():
    return Machine("draft", [
        Transition("draft", "submit", "review"),
        Transition("review", "approve", "published",
                   guard=lambda c: c.get("is_admin", False)),
        Transition("review", "reject", "draft"),
    ])


def test_unknown_event_raises():
    with pytest.raises(UnknownTransition):
        _machine().fire("explode")


def test_event_valid_from_another_state_raises():
    # "approve" exists, but not from "draft".
    with pytest.raises(UnknownTransition):
        _machine().fire("approve")


def test_rejected_guard_leaves_history_untouched():
    m = _machine()
    m.fire("submit")
    before = list(m.history)
    m.fire("approve", {"is_admin": False})
    assert m.history == before


def test_passing_guard_moves_the_machine():
    m = _machine()
    m.fire("submit")
    assert m.fire("approve", {"is_admin": True}) is True
    assert m.state == "published"


def test_history_records_each_move_in_order():
    m = _machine()
    m.fire("submit")
    m.fire("reject")
    assert m.history == ["draft", "review", "draft"]


def test_guard_receives_the_context():
    seen = {}
    m = Machine("a", [Transition("a", "go", "b", guard=lambda c: seen.update(c) or True)])
    m.fire("go", {"k": 1})
    assert seen == {"k": 1}


def test_guardless_transition_always_moves():
    m = Machine("a", [Transition("a", "go", "b")])
    assert m.fire("go") is True
    assert m.state == "b"
