from authz.check import can
from authz.roles import ALLOW, DENY


def test_deny_deeper_in_chain_beats_nearer_allow():
    roles = {
        "base": {"parents": [], "rules": {"write": DENY}},
        "mid": {"parents": ["base"], "rules": {"write": ALLOW}},
        "leaf": {"parents": ["mid"], "rules": {}},
    }
    assert can(roles, "leaf", "write") is False


def test_deny_in_any_branch_wins():
    roles = {
        "a": {"parents": [], "rules": {"read": ALLOW}},
        "b": {"parents": [], "rules": {"read": DENY}},
        "leaf": {"parents": ["a", "b"], "rules": {}},
    }
    assert can(roles, "leaf", "read") is False


def test_inherited_allow_without_deny():
    roles = {
        "admin": {"parents": [], "rules": {"delete": ALLOW}},
        "staff": {"parents": ["admin"], "rules": {}},
    }
    assert can(roles, "staff", "delete") is True


def test_no_rule_anywhere_is_denied_by_default():
    roles = {"guest": {"parents": [], "rules": {}}}
    assert can(roles, "guest", "delete") is False


def test_unknown_role_denied():
    assert can({}, "ghost", "read") is False


def test_role_cycle_terminates():
    roles = {
        "a": {"parents": ["b"], "rules": {}},
        "b": {"parents": ["a"], "rules": {}},
    }
    assert can(roles, "a", "read") is False


def test_cycle_with_allow_still_resolves():
    roles = {
        "a": {"parents": ["b"], "rules": {}},
        "b": {"parents": ["a"], "rules": {"read": ALLOW}},
    }
    assert can(roles, "a", "read") is True
