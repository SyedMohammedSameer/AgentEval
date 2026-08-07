from conf.loader import load_layers
from conf.merge import deep_merge


def test_three_layers_accumulate():
    layers = [{"a": {"x": 1, "y": 2}}, {"a": {"y": 3}}, {"a": {"z": 4}}]
    assert load_layers(layers) == {"a": {"x": 1, "y": 3, "z": 4}}


def test_deeply_nested():
    base = {"a": {"b": {"c": 1, "d": 2}}}
    assert deep_merge(base, {"a": {"b": {"d": 9}}}) == {"a": {"b": {"c": 1, "d": 9}}}


def test_non_dict_replaces_dict():
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


def test_dict_replaces_non_dict():
    assert deep_merge({"a": 5}, {"a": {"b": 1}}) == {"a": {"b": 1}}


def test_inputs_not_mutated():
    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    deep_merge(base, override)
    assert base == {"a": {"b": 1}}
    assert override == {"a": {"c": 2}}


def test_empty_layers():
    assert load_layers([]) == {}
