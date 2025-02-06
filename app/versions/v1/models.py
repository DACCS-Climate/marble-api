from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class DataRequestBase(SQLModel):
    """
    SQL model base object for Data Requests.

    This object contains field validators.
    """

    @field_validator("title", check_fields=False)
    def validate_title(cls, title: str) -> str:
        """Check that the title field does not have a space in it."""
        if title and " " in title:
            raise ValueError("title cannot contain space characters")
        return title

    # TODO: add additional validators here


class DataRequest(DataRequestBase, table=True):
    """
    Database model for Data Requests.

    This object contains the representation of the data in the database.
    """

    id: int | None = Field(default=None, primary_key=True)
    title: str
    desc: str
    date: datetime
    # TODO: add more parameters


class DataRequestPublic(DataRequestBase):
    """
    Public model for Data Requests.

    This object contains all fields that are visible to users.
    If a field defined in DataRequests should not be visible to users, it will not
    be included in this object.
    """

    id: int
    title: str
    desc: str
    date: datetime
    # TODO: copy any parameters from DataRequest that should be visible to the user here


class DataRequestUpdate(DataRequestBase):
    """
    Update model for Data Requests.

    This object contains all fields that are updatable on the DataRequest model.
    Fields should be optional unless they *must* be updated every time a change is made.
    """

    title: str | None = None
    desc: str | None = None
    date: datetime | None = None
    # TODO: make sure parameters added in DataRequest are made optional here
