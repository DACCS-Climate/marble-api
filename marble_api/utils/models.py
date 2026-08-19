from copy import deepcopy
from typing import Annotated, Any

import bson
from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    FieldSerializationInfo,
    computed_field,
    create_model,
    field_serializer,
)
from pydantic.fields import FieldInfo
from pydantic.json_schema import SkipJsonSchema

PyObjectId = Annotated[str, BeforeValidator(str)]


def partial_model(model: type[BaseModel]) -> type[BaseModel]:
    """
    Make all fields in a BaseModel class optional.

    This makes each field's default None but does not update the annotation or
    validations so explicitly setting the value to None may still raise a
    validation error. Also, if a field has validate_default=True this will
    make validate_default=False for the partial model to ensure that the new
    (None) default value is not validated.

    >>> class C(BaseModel):
          a: int
    >>> C(a=2).a
    2
    >>> C()  # validation error since a must be an integer
    >>> @partial_model
    ... class B(C): ...
    >>> B().a  # is None
    >>> B(a=5).a
    5
    >>> B(a=None)  # validation error since a must be an integer

    Adapted from https://stackoverflow.com/a/76560886/5992438
    """

    def make_field_optional(field: FieldInfo) -> tuple[Any, FieldInfo]:
        new_field = deepcopy(field)
        new_field.validate_default = False
        new_field.default = None
        return new_field.annotation, new_field

    return create_model(
        model.__name__,
        __base__=model,
        __module__=model.__module__,
        **{name: make_field_optional(info) for name, info in model.model_fields.items()},
    )


def object_id(id_: str, error: Exception | None) -> bson.ObjectId:
    """
    Convert id_ to a bson.ObjectId.

    Raises error from bson.errors.InvalidId if error is provided
    """
    try:
        return bson.ObjectId(id_)
    except bson.errors.InvalidId as err:
        if error is not None:
            raise error from err


class MarbleBaseModel(BaseModel):
    """
    Base model for all database models used in this repo.

    Includes:
        - an id stored as a PyObjectId in the database
        - created field calculated from the id value
        - updated field that should be updated by the route
    """

    id: SkipJsonSchema[PyObjectId | None] = Field(default=None, validation_alias="_id", exclude=True)
    updated: SkipJsonSchema[AwareDatetime | None] = None  # updated should set by the route
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True)


class MarbleBaseModelUpdate(MarbleBaseModel):
    """
    Base model for update models in this repo.

    Sets the model_config without validate_by_name=True to ensure that the id cannot easily be overwritten.

    NOTE: the child class that inherits from this should also be decorated with the partial_model function
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={bson.ObjectId: str})


class MarbleBaseModelPublic(MarbleBaseModel):
    """
    Base model for public models (visible to the end user) in this repo.

    Makes the id and updated fields visible and creates a computed field for model creation time.
    """

    id: Annotated[str, BeforeValidator(str)] = Field(..., validation_alias="_id")
    updated: AwareDatetime
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True, extra="allow")

    @computed_field
    def created(self) -> AwareDatetime:
        """Set the created time based on the object id."""
        return object_id(self.id, None).generation_time


class MarbleUserModel(MarbleBaseModel):
    """
    Base model for models that are associated with a user.

    Requires that the user attribute is set when serialized.
    """

    user: SkipJsonSchema[str | None] = None  # user is set by the route after the model is first validated

    @field_serializer("user")
    def require_user_set(self, value: str, info: FieldSerializationInfo) -> str:
        """Require that the user name be set when the model is serialized."""
        assert value, f"{info.field_name} must be set and non-empty"
        return value


class MarbleUserModelUpdate(MarbleBaseModelUpdate, MarbleUserModel):
    """Base model for updating user associated models."""


class MarbleUserModelPublic(MarbleBaseModelPublic, MarbleUserModel):
    """Base model for public models associated with a user."""

    user: str  # user is required to be set in the database
