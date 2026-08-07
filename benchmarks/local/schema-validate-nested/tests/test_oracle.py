from schema.types import Field
from schema.validate import validate


def test_nested_errors_are_reported_with_dotted_path():
    schema = {
        "user": Field("object", fields={
            "address": Field("object", fields={"city": Field("str")}),
        }),
    }
    errors = validate({"user": {"address": {}}}, schema)
    assert errors == ["user.address.city: missing required field"]


def test_nested_type_error():
    schema = {"user": Field("object", fields={"age": Field("int")})}
    errors = validate({"user": {"age": "old"}}, schema)
    assert errors == ["user.age: expected int, got str"]


def test_valid_nested_value_has_no_errors():
    schema = {"user": Field("object", fields={"name": Field("str")})}
    assert validate({"user": {"name": "ada"}}, schema) == []


def test_optional_nested_object_absent_is_fine():
    schema = {"meta": Field("object", required=False, fields={"k": Field("str")})}
    assert validate({}, schema) == []


def test_optional_field_present_is_still_type_checked():
    assert validate({"nick": 5}, {"nick": Field("str", required=False)}) == [
        "nick: expected str, got int"
    ]


def test_top_level_type_error_short_circuits_nesting():
    schema = {"user": Field("object", fields={"name": Field("str")})}
    assert validate({"user": "nope"}, schema) == ["user: expected object, got str"]


def test_multiple_errors_collected():
    schema = {"a": Field("str"), "b": Field("int")}
    errors = validate({}, schema)
    assert len(errors) == 2
