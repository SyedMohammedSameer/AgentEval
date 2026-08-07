from query.compose import all_of, any_of, filter_rows, none_of
from query.predicates import contains, eq, gt

ROWS = [
    {"name": "ada", "age": 36},
    {"name": "bob", "age": 20},
    {"name": "cy", "age": 50},
]


def test_none_of_consults_every_predicate():
    got = filter_rows(ROWS, none_of(eq("name", "ada"), eq("name", "bob")))
    assert got == [ROWS[2]]


def test_any_of_with_no_matching_predicate():
    assert filter_rows(ROWS, any_of(eq("name", "zz"))) == []


def test_empty_any_of_matches_nothing():
    assert filter_rows(ROWS, any_of()) == []


def test_empty_all_of_matches_everything():
    assert filter_rows(ROWS, all_of()) == ROWS


def test_empty_none_of_matches_everything():
    assert filter_rows(ROWS, none_of()) == ROWS


def test_nested_composition():
    pred = all_of(gt("age", 25), any_of(eq("name", "ada"), eq("name", "cy")))
    assert filter_rows(ROWS, pred) == [ROWS[0], ROWS[2]]


def test_none_of_wrapping_a_composite():
    assert filter_rows(ROWS, none_of(any_of(eq("name", "ada"), eq("name", "cy")))) == [ROWS[1]]


def test_missing_fields_never_match():
    assert filter_rows(ROWS, contains("bio", "x")) == []
    assert filter_rows([{"name": "x"}], gt("age", 1)) == []
