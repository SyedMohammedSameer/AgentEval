ALLOW = "allow"
DENY = "deny"


class RoleGraph:
    def __init__(self, roles: dict):
        """roles: name -> {"parents": [...], "rules": {action: ALLOW|DENY}}"""
        self.roles = roles

    def parents_of(self, role: str) -> list:
        return self.roles.get(role, {}).get("parents", [])

    def rule_for(self, role: str, action: str):
        return self.roles.get(role, {}).get("rules", {}).get(action)
