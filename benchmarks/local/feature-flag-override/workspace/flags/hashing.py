import hashlib


def bucket_of(flag: str, user_id: str) -> int:
    """Stable bucket in [0, 100) for a (flag, user) pair."""
    digest = hashlib.sha256(f"{flag}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100
