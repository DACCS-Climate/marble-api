import re
from contextlib import suppress
from typing import Annotated, Any

import bson
from bson.regex import Regex as BsonRegex
from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    FieldSerializationInfo,
    PydanticUndefinedAnnotation,
    computed_field,
    field_serializer,
)
from pydantic.json_schema import SkipJsonSchema


def _convert_bson_regex(value: Any) -> str | re.Pattern:  # noqa: ANN401
    """
    Convert bson.regex.Regex to a python re.Pattern.

    MongoDB will return regular expressions as bson.regex.Regex which
    pydantic doensn't know how to convert to a re.Pattern without help.
    """
    if isinstance(value, BsonRegex):
        return value.try_compile()
    return value


type PyObjectId = Annotated[str, BeforeValidator(str)]
type Pattern = Annotated[re.Pattern, BeforeValidator(_convert_bson_regex)]


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


class PartialModel(BaseModel):
    """Superclass for partial models (all fields are optional)."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        """
        Make all models that this model a "partial model".

        Partial models make all fields optional.

        This sets all fields to have a default value of None but don't update the annotation
        so that fields can't explicitly be set to None.
        """
        super().__pydantic_init_subclass__(**kwargs)
        for field in cls.model_fields.values():
            field.default = None

        with suppress(PydanticUndefinedAnnotation):
            cls.model_rebuild(force=True)


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
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True, validate_assignment=True)


class MarbleBaseModelUpdate(PartialModel, MarbleBaseModel):
    """
    Base model for update models in this repo.

    Ensures that subclasses of this model are partial models (all fields are optional)
    """


class MarbleBaseModelPublic(MarbleBaseModel):
    """
    Base model for public models (visible to the end user) in this repo.

    Makes the id and updated fields visible and creates a computed field for model creation time.

    Sets extra=allow so additional data can be added to models returned by route methods.
    Does not set validate_assignment=True to allow flexibility when routes add/update data.
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
    def require_user_set(self, value: str, info: FieldSerializationInfo) -> SkipJsonSchema[str]:
        """Require that the user name be set when the model is serialized."""
        if not value:
            raise ValueError(f"{info.field_name} must be set and non-empty")
        return value


class MarbleUserModelUpdate(MarbleBaseModelUpdate, MarbleUserModel):
    """Base model for updating user associated models."""


class MarbleUserModelPublic(MarbleBaseModelPublic, MarbleUserModel):
    """Base model for public models associated with a user."""

    user: str = Field(..., min_length=1)  # user is required to be set in the database

    # NOTE: this must be redeclared so that the return annotation can be modified to
    #       allow the user field to show up in the JSON schema.
    @field_serializer("user")
    def require_user_set(self, value: str, info: FieldSerializationInfo) -> str:
        """Require that the user name be set when the model is serialized."""
        return super().require_user_set(value, info)
