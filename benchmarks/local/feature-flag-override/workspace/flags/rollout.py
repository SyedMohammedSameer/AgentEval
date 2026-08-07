from flags.hashing import bucket_of


class FlagSet:
    def __init__(self, flags: dict):
        """flags: name -> {"percent": 0..100, "overrides": {user_id: bool}}"""
        self.flags = flags

    def is_enabled(self, flag: str, user_id: str) -> bool:
        spec = self.flags.get(flag)
        if spec is None:
            return False
        percent = spec.get("percent", 0)
        # BUG: `<=` admits bucket 0 even when percent is 0, so a flag that is
        # fully off still fires for one bucket's worth of users.
        if bucket_of(flag, user_id) <= percent:
            return True
        # BUG: overrides are only reached when the rollout says no, so an
        # explicit False override can never turn a flag off.
        return spec.get("overrides", {}).get(user_id, False)
