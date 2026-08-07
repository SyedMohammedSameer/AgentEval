from urlkit.encode import build_query, quote


def test_simple_pair():
    assert build_query({"q": "hello"}) == "q=hello"


def test_reserved_characters_are_escaped():
    assert quote("a&b") == "a%26b"
