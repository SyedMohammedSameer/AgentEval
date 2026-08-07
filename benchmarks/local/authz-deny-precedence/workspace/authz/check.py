from authz.roles import ALLOW, DENY, RoleGraph


def can(roles: dict, role: str, action: str) -> bool:
    """True if `role` may perform `action`."""
    graph = RoleGraph(roles)

    def resolve(name: str):
        # BUG: the first rule found wins and the walk returns immediately, so an
        # inherited ALLOW can be returned before a DENY deeper in the chain is
        # ever considered. BUG: nothing tracks visited roles, so a parent cycle
        # recurses forever.
        rule = graph.rule_for(name, action)
        if rule is not None:
            return rule
        for parent in graph.parents_of(name):
            found = resolve(parent)
            if found is not None:
                return found
        return None

    return resolve(role) == ALLOW
