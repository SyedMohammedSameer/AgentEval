from fsm.machine import Machine
from fsm.transitions import Transition


def _machine():
    return Machine("draft", [
        Transition("draft", "submit", "review"),
        Transition("review", "approve", "published",
                   guard=lambda c: c.get("is_admin", False)),
    ])


def test_simple_transition():
    m = _machine()
    assert m.fire("submit") is True
    assert m.state == "review"


def test_rejected_guard_does_not_move_state():
    m = _machine()
    m.fire("submit")
    assert m.fire("approve", {"is_admin": False}) is False
    assert m.state == "review"
