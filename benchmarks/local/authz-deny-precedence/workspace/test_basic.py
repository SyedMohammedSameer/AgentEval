from authz.check import can
from authz.roles import ALLOW, DENY


def test_direct_allow():
    roles = {"admin": {"parents": [], "rules": {"delete": ALLOW}}}
    assert can(roles, "admin", "delete") is True


def test_deny_further_up_the_chain_still_wins():
    roles = {
        "base": {"parents": [], "rules": {"write": DENY}},
        "mid": {"parents": ["base"], "rules": {"write": ALLOW}},
        "leaf": {"parents": ["mid"], "rules": {}},
    }
    assert can(roles, "leaf", "write") is False
