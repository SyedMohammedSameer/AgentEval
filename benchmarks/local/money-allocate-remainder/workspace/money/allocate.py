def allocate(amount: int, weights: list[float]) -> list[int]:
    """Split `amount` cents across `weights`, returning whole cents."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if not weights or sum(weights) <= 0:
        raise ValueError("weights must be non-empty and sum to a positive value")

    total = sum(weights)
    # BUG: each part is rounded independently, so the parts can sum to more or
    # less than `amount` - the remainder is never reconciled.
    return [round(amount * w / total) for w in weights]
