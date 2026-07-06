from brackets import is_balanced


def test_wrong_order():
    assert is_balanced("([)]") is False


def test_wrong_type():
    assert is_balanced("(]") is False


def test_nested_ok():
    assert is_balanced("{[()()]}") is True


def test_empty():
    assert is_balanced("") is True
