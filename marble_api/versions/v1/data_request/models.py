from collections.abc import Sized
from typing import Required, TypedDict

from bson import ObjectId
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
)
from pydantic.functional_validators import BeforeValidator
from pydantic.json_schema import SkipJsonSchema
from stac_pydantic.item import Item
from stac_pydantic.links import Links
from typing_extensions import Annotated

from marble_api.utils.geojson import Geometry, bbox_from_coordinates
from marble_api.utils.models import partial_model

PyObjectId = Annotated[str, BeforeValidator(str)]
Temporal = Annotated[list[AwareDatetime], Field(..., min_length=1, max_length=2), AfterValidator(sorted)]


class Author(TypedDict, total=False):
    """Author definition."""

    first_name: str | None = None
    last_name: Required[str]
    email: EmailStr | None = None


class DataRequest(BaseModel):
    """
    Database model for Data Requests.

    This object contains the representation of the data in the database.
    """

    id: SkipJsonSchema[PyObjectId | None] = Field(default=None, validation_alias="_id", exclude=True)
    user: str
    title: str
    description: str | None = None
    authors: list[Author]
    geometry: Geometry | None
    temporal: Temporal
    links: Links
    path: str
    contact: EmailStr
    additional_paths: list[str] = []
    variables: list[str] = []
    extra_properties: dict[str, str] = {}
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    @field_validator("user", "title", "description", "authors", "path", "contact")
    @classmethod
    def min_length_if_set(cls, value: Sized | None, info: ValidationInfo) -> Sized | None:
        """Raise an error if the value is not None and is empty."""
        assert value is None or len(value), f"{info.field_name} must be None or non-empty"
        return value


@partial_model
class DataRequestUpdate(DataRequest):
    """
    Update model for Data Requests.

    This object contains all fields that are updatable on the DataRequest model.
    Fields should be optional unless they *must* be updated every time a change is made.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={ObjectId: str})


class DataRequestPublic(DataRequest):
    """
    Public model for Data Requests.

    This allows for the id field to be included in the response extra fields (like stac_item) so that they can be visible in API responses.
    """

    id: Annotated[str, BeforeValidator(str)] = Field(..., validation_alias="_id")
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="allow")

    @property
    def stac_item(self) -> Item:
        """Dynamically create a STAC item representation of this data."""
        item = {
            "type": "Feature",
            "stac_version": "1.1.0",
            "geometry": self.geometry and self.geometry.model_dump(),
            "stac_extensions": [],  # TODO
            "id": self.id,  # TODO
            "bbox": None,
            "properties": dict(self.extra_properties),  # TODO: add more
            "links": self.links.model_dump(),
            "assets": {},  # TODO: determine assets from other fields
        }

        # STAC spec recommends including datetime even if using start_datetime and end_datetime
        # See: https://github.com/radiantearth/stac-spec/blob/master/best-practices.md#datetime-selection
        item["properties"]["datetime"] = self.temporal[0].isoformat()

        if len(set(self.temporal)) > 1:
            item["properties"]["start_datetime"], item["properties"]["end_datetime"] = [
                t.isoformat() for t in self.temporal
            ]

        if self.geometry:
            item["bbox"] = item["geometry"].get("bbox") or bbox_from_coordinates(self.geometry.coordinates)
        return item


class DataRequestsResponse(BaseModel):
    """Response model for returning multiple data requests."""

    data_requests: list[DataRequestPublic]
    links: Links
