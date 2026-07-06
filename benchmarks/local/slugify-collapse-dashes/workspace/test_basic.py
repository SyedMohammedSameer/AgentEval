from textutils import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"


def test_trailing_punct():
    assert slugify("Hello!!!") == "hello"
