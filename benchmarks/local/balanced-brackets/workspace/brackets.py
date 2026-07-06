def is_balanced(s: str) -> bool:
    # BUG: only counts totals, ignores order and bracket type.
    opens = sum(s.count(c) for c in "([{")
    closes = sum(s.count(c) for c in ")]}")
    return opens == closes
