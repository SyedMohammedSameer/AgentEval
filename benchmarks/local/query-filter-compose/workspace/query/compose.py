def all_of(*predicates):
    """Match rows satisfying every predicate."""
    def check(row):
        for p in predicates:
            if not p(row):
                return False
        return True
    return check


def any_of(*predicates):
    """Match rows satisfying at least one predicate."""
    def check(row):
        for p in predicates:
            if p(row):
                return True
        # BUG: falling through returns True, so any_of matches every row and
        # silently disables whatever filtering it was supposed to express.
        return True
    return check


def none_of(*predicates):
    """Match rows satisfying no predicate."""
    def check(row):
        # BUG: only the first predicate is negated; the rest are ignored.
        return not predicates[0](row) if predicates else True
    return check


def filter_rows(rows, predicate):
    return [r for r in rows if predicate(r)]
