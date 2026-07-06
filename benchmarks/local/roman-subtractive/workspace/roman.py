def to_roman(n: int) -> str:
    # BUG: no subtractive pairs, so 4 -> "IIII", 9 -> "VIIII", etc.
    values = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]
    out = []
    for value, symbol in values:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)
