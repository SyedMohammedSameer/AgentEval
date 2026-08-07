from logrotate.naming import sort_rotations
from logrotate.retention import files_to_delete


def test_sort_is_numeric_not_lexical():
    files = ["app.log.1", "app.log.2", "app.log.10"]
    assert sort_rotations(files) == ["app.log.1", "app.log.2", "app.log.10"]


def test_keeps_exactly_the_requested_number():
    files = ["app.log.1", "app.log.2", "app.log.3"]
    assert files_to_delete(files, keep=2) == ["app.log.3"]
