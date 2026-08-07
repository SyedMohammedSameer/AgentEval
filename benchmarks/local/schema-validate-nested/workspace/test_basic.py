from schema.types import Field
from schema.validate import validate


def test_missing_required_reported():
    errors = validate({}, {"name": Field("str")})
    assert errors == ["name: missing required field"]


def test_optional_field_may_be_absent():
    assert validate({}, {"nick": Field("str", required=False)}) == []
