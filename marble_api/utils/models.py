from copy import deepcopy
from typing import Any

import bson
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo


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
