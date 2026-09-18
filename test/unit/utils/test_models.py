import datetime

import bson
import pytest
from pydantic import ValidationError, field_validator
from pydantic_core import PydanticSerializationError

from marble_api.utils.models import (
    MarbleBaseModel,
    MarbleBaseModelPublic,
    MarbleBaseModelUpdate,
    MarbleUserModel,
    MarbleUserModelPublic,
    MarbleUserModelUpdate,
    PartialModel,
    object_id,
)


class TestPartial:
    @pytest.fixture
    def partial_class(self):
        class PModel(PartialModel):
            a: int
            b: str = None

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


def _create_model_func(klass, **kwargs):
    def _(unset=None, _klass=klass, _kwargs=kwargs, **kw):
        kwargs_ = {k: v for k, v in {**_kwargs, **kw}.items() if k not in (unset or [])}
        return _klass(**kwargs_)

    return _


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


class TestMarbleBaseModel:
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(MarbleBaseModel, id=bson.ObjectId())

    def test_id_not_dumped(self, fake_class):
        assert "id" not in fake_class().model_dump()

    def test_fields_not_in_schema(self, fake_class):
        schema_properties = fake_class().model_json_schema(mode="serialization")["properties"]
        assert not {"id", "user", "updated"} & set(schema_properties)

    def test_updated_tz_aware(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class().updated = datetime.datetime.now()
        fake_class().updated = datetime.datetime.now(tz=datetime.timezone.utc)

    def test_extra_not_allowed(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class().extra = 10


class TestMarbleBaseModelUpdate:
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(MarbleBaseModelUpdate, id=bson.ObjectId())

    def test_partial_model(self, fake_class):
        assert issubclass(type(fake_class()), PartialModel)

    def test_extra_not_allowed(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class().extra = 10


class TestMarbleBaseModelPublic:
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(
            MarbleBaseModelPublic, id=bson.ObjectId(), updated=datetime.datetime.now(tz=datetime.timezone.utc)
        )

    def test_id_dumped(self, fake_class):
        assert "id" in fake_class().model_dump()

    def test_fields_in_schema(self, fake_class):
        fields = fake_class().model_json_schema(mode="serialization")["properties"]
        assert all(field in fields for field in ["id", "updated", "created"])

    def test_allow_extras(self, fake_class):
        instance = fake_class()
        instance.extra = 10
        assert instance.model_dump()["extra"] == 10

    def test_created_computed_field(self, fake_class):
        instance = fake_class()
        assert instance.created == bson.ObjectId(instance.id).generation_time


class _UserTests:
    def test_user(self, fake_class):
        instance = fake_class()
        assert instance.model_dump()["user"] == instance.user


class TestMarbleUserModel(TestMarbleBaseModel, _UserTests):
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(MarbleUserModel, id=bson.ObjectId(), user="test-user")

    def test_user_set_when_serialized(self, fake_class):
        with pytest.raises(PydanticSerializationError):
            fake_class(unset=["user"]).model_dump()


class TestMarbleUserModelUpdate(TestMarbleBaseModelUpdate, _UserTests):
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(MarbleUserModelUpdate, user="test-user")


class TestMarbleUserModelPublic(TestMarbleBaseModelPublic, _UserTests):
    @pytest.fixture
    def fake_class(self):
        return _create_model_func(
            MarbleUserModelPublic,
            id=bson.ObjectId(),
            updated=datetime.datetime.now(tz=datetime.timezone.utc),
            user="test-user",
        )

    def test_fields_in_schema(self, fake_class):
        fields = fake_class().model_json_schema(mode="serialization")["properties"]
        assert all(field in fields for field in ["id", "updated", "created", "user"])

    @pytest.mark.parametrize("value", [None, ""])
    def test_user_field_required(self, value, fake_class):
        with pytest.raises(ValidationError):
            fake_class(user=value)
