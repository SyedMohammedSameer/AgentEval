from textutils import slugify


def test_multiple_spaces():
    assert slugify("a   b") == "a-b"


def test_leading_trailing():
    assert slugify("  Hello World  ") == "hello-world"


def test_mixed_punct():
    assert slugify("Foo -- Bar/Baz") == "foo-bar-baz"


def test_numbers_kept():
    assert slugify("Route 66!") == "route-66"
