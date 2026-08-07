from flags.hashing import bucket_of


class FlagSet:
    def __init__(self, flags: dict):
        """flags: name -> {"percent": 0..100, "overrides": {user_id: bool}}"""
        self.flags = flags

    def is_enabled(self, flag: str, user_id: str) -> bool:
        spec = self.flags.get(flag)
        if spec is None:
            return False
        # An override is an explicit decision and outranks the rollout in both
        # directions, so it is consulted before the bucket is computed.
        overrides = spec.get("overrides", {})
        if user_id in overrides:
            return overrides[user_id]
        # `percent` is the share of buckets strictly below it: at 0 nothing
        # qualifies, at 100 every bucket in [0, 100) does.
        return bucket_of(flag, user_id) < spec.get("percent", 0)
