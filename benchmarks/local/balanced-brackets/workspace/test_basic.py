from brackets import is_balanced


def test_ok():
    assert is_balanced("()[]{}") is True


def test_bad_count():
    assert is_balanced("(()") is False
