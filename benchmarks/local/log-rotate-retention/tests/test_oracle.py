import pytest

from logrotate.naming import parse_index, rotated_name, sort_rotations
from logrotate.retention import files_to_delete


def test_double_digit_indices_order_correctly():
    files = [f"app.log.{i}" for i in (3, 11, 1, 22, 2)]
    assert sort_rotations(files) == [
        "app.log.1", "app.log.2", "app.log.3", "app.log.11", "app.log.22",
    ]


def test_retention_across_double_digits():
    files = [f"app.log.{i}" for i in range(1, 13)]
    assert files_to_delete(files, keep=3) == [f"app.log.{i}" for i in range(4, 13)]


def test_keep_zero_deletes_every_rotation():
    assert files_to_delete(["app.log.1", "app.log.2"], keep=0) == ["app.log.1", "app.log.2"]


def test_unrotated_files_are_never_deleted():
    files = ["app.log", "app.log.1", "app.log.2"]
    assert "app.log" not in files_to_delete(files, keep=0)


def test_keep_more_than_exists():
    assert files_to_delete(["app.log.1"], keep=5) == []


def test_parse_index():
    assert parse_index("app.log.7") == 7
    assert parse_index("app.log") is None
    assert parse_index(rotated_name("app.log", 4)) == 4


def test_negative_keep_rejected():
    with pytest.raises(ValueError):
        files_to_delete(["app.log.1"], keep=-1)
