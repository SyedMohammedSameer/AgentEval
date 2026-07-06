from graph import has_cycle


def test_simple_cycle():
    assert has_cycle({"a": ["b"], "b": ["a"]}) is True


def test_no_cycle():
    assert has_cycle({"a": ["b"], "b": []}) is False
