from conf.loader import load_layers


def test_flat_override():
    assert load_layers([{"a": 1}, {"a": 2}]) == {"a": 2}


def test_nested_sibling_survives():
    layers = [{"db": {"host": "localhost", "port": 5432}}, {"db": {"port": 6000}}]
    assert load_layers(layers) == {"db": {"host": "localhost", "port": 6000}}
