def allocate(amount: int, weights: list[float]) -> list[int]:
    """Split `amount` cents across `weights`, returning whole cents."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if not weights or sum(weights) <= 0:
        raise ValueError("weights must be non-empty and sum to a positive value")

    total = sum(weights)
    exact = [amount * w / total for w in weights]
    parts = [int(x) for x in exact]           # floor, so the sum never overshoots

    # Hand the shortfall out one cent at a time, largest fractional part first.
    remainder = amount - sum(parts)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(exact[i] - parts[i]), i),
    )
    for i in order[:remainder]:
        parts[i] += 1
    return parts
