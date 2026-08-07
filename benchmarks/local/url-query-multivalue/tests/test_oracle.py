from urlkit.encode import build_query, quote
from urlkit.parse import parse_query, unquote


def test_list_value_repeats_the_key():
    assert build_query({"tag": ["a", "b"]}) == "tag=a&tag=b"


def test_space_becomes_plus():
    assert build_query({"q": "hello world"}) == "q=hello+world"


def test_equals_in_value_is_escaped():
    assert build_query({"q": "a=b"}) == "q=a%3Db"


def test_round_trip_preserves_multivalue_and_reserved_chars():
    params = {"tag": ["x", "y"], "q": "a&b=c"}
    assert parse_query(build_query(params)) == {"tag": ["x", "y"], "q": ["a&b=c"]}


def test_round_trip_with_spaces():
    assert parse_query(build_query({"q": "hello world"})) == {"q": ["hello world"]}


def test_unicode_is_percent_encoded_as_utf8():
    assert quote("\u00e9") == "%C3%A9"
    assert unquote("%C3%A9") == "\u00e9"


def test_unreserved_characters_pass_through():
    assert quote("a-_.~Z9") == "a-_.~Z9"


def test_empty_inputs():
    assert build_query({}) == ""
    assert parse_query("") == {}
