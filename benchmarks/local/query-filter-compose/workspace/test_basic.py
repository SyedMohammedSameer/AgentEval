from query.compose import all_of, any_of, filter_rows
from query.predicates import eq, gt

ROWS = [
    {"name": "ada", "age": 36},
    {"name": "bob", "age": 20},
    {"name": "cy", "age": 50},
]


def test_all_of():
    assert filter_rows(ROWS, all_of(gt("age", 30), eq("name", "ada"))) == [ROWS[0]]


def test_any_of_does_not_match_everything():
    got = filter_rows(ROWS, any_of(eq("name", "ada"), eq("name", "bob")))
    assert got == [ROWS[0], ROWS[1]]
