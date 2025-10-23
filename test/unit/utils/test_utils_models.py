import bson
import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

from marble_api.utils.models import object_id, partial_model


class TestPartial:
    @pytest.fixture
    def partial_class(self):
        @partial_model
        class PModel(BaseModel):
            a: int
            b: str = Field(None, validate_default=True)

            @field_validator("b")
            @classmethod
            def not_none(cls, value):
                assert value is not None
                return value

        return PModel

    def test_nothing_required(self, partial_class):
        assert partial_class().model_dump() == {"a": None, "b": None}

    def test_field_without_default_settable(self, partial_class):
        assert partial_class(a=10).model_dump() == {"a": 10, "b": None}

    def test_field_with_default_settable(self, partial_class):
        assert partial_class(b="other").model_dump() == {"a": None, "b": "other"}

    def test_validations_still_work(self, partial_class):
        with pytest.raises(ValidationError):
            partial_class(a="some string")

    def test_no_default_validation(self, partial_class):
        with pytest.raises(ValidationError):
            partial_class(b=None)


class TestObjectId:
    def test_valid_id(self):
        id_ = bson.ObjectId()
        assert id_ == object_id(str(id_), Exception)

    def test_invalid_id(self):
        with pytest.raises(Exception):
            object_id("invalid string", Exception)

    def test_invalid_id_custom_exception(self):
        class MyCustomException(Exception): ...

        with pytest.raises(MyCustomException):
            object_id("invalid string", MyCustomException)

    def test_invalid_id_custom_message(self):
        with pytest.raises(Exception) as e:
            msg = "here is a message"
            object_id("invalid string", Exception(msg))
            assert msg == str(e)
