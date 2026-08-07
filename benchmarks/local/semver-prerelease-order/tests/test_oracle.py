import pytest

from semver.compare import compare
from semver.parse import parse


def test_numeric_identifiers_compare_numerically():
    assert compare("1.0.0-2", "1.0.0-10") == -1


def test_numeric_lower_than_alphanumeric():
    assert compare("1.0.0-1", "1.0.0-alpha") == -1


def test_more_identifiers_wins_when_prefix_equal():
    assert compare("1.0.0-alpha", "1.0.0-alpha.1") == -1


def test_documented_precedence_chain():
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    for lo, hi in zip(chain, chain[1:]):
        assert compare(lo, hi) == -1, f"{lo} should precede {hi}"
        assert compare(hi, lo) == 1


def test_equality():
    assert compare("2.3.4", "2.3.4") == 0
    assert compare("2.3.4-rc.1", "2.3.4-rc.1") == 0


def test_major_minor_dominate():
    assert compare("2.0.0", "1.99.99") == 1
    assert compare("1.2.0", "1.1.99") == 1


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse("not.a.version")
