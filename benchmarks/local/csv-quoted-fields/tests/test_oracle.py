from csvlite.reader import parse, parse_line


def test_escaped_quote_inside_quoted_field():
    assert parse_line('a,"say ""hi""",b') == ["a", 'say "hi"', "b"]


def test_quoted_field_only():
    assert parse_line('"hello"') == ["hello"]


def test_empty_fields_preserved():
    assert parse_line("a,,b") == ["a", "", "b"]
    assert parse_line(",") == ["", ""]


def test_empty_quoted_field():
    assert parse_line('a,"",b') == ["a", "", "b"]


def test_quote_not_at_field_start_is_literal():
    assert parse_line("a,b\"c,d") == ["a", 'b"c', "d"]


def test_trailing_quoted_field():
    assert parse_line('a,"b,c"') == ["a", "b,c"]


def test_multiple_rows():
    doc = 'name,note\nalice,"likes a,b"\nbob,plain'
    assert parse(doc) == [["name", "note"], ["alice", "likes a,b"], ["bob", "plain"]]
