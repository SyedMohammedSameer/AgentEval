from authz.roles import ALLOW, DENY, RoleGraph


def can(roles: dict, role: str, action: str) -> bool:
    """True if `role` may perform `action`."""
    graph = RoleGraph(roles)
    seen: set = set()
    found_allow = False

    def walk(name: str) -> bool:
        """Visit the chain, returning True as soon as a DENY is seen."""
        nonlocal found_allow
        if name in seen:
            return False
        seen.add(name)

        rule = graph.rule_for(name, action)
        if rule == DENY:
            return True
        if rule == ALLOW:
            found_allow = True

        # Keep walking even after an ALLOW: a deny further up must still win.
        for parent in graph.parents_of(name):
            if walk(parent):
                return True
        return False

    denied = walk(role)
    return found_allow and not denied
