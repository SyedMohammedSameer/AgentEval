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
        # No predicate matched - and an empty any_of is vacuously false.
        return False
    return check


def none_of(*predicates):
    """Match rows satisfying no predicate."""
    inner = any_of(*predicates)

    def check(row):
        return not inner(row)
    return check


def filter_rows(rows, predicate):
    return [r for r in rows if predicate(r)]
