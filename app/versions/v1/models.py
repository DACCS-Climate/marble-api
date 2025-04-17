from datetime import datetime

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from fastapi import FastAPI
from typing import List

app = FastAPI(version="1")


class DataRequestBase(SQLModel):
    """
    SQL model base object for Data Requests.

    This object contains field validators.
    """
    start_date: datetime
    end_date: datetime

    @model_validator(mode="before")
    def validate_timeperiod(cls, values):
        start_time = values.__dict__.get("start_date")
        end_time = values.__dict__.get("end_date")
        try:
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}")
        # Check if the end date is earlier than the start date
        if end_time < start_time:
            raise ValueError("End date cannot be earlier than start date.")

        return values  # Does nothing, just returns the values as they are
    
    @model_validator(mode="before")
    def validate_location(cls, values):
        """Ensure list lengths match and check latitude/longitude validity."""
        lat = values.__dict__.get("latitude")
        lon = values.__dict__.get("longitude")
        file = values.__dict__.get("myFile")
        """Ensure list lengths match."""
        #if len(latitude) != len(longitude):
        #    raise ValueError("Latitude and longitude lists are different lengths")
        """If there is no latitude and longitude, make sure there is a GeoJSON"""
        if lat is None and file is None:
            raise ValueError("Must include either GeoJSON file or manually inputted latitude and longitudes")
        """Check latitude and longitude ranges"""
        if lat > 90 or lat < -90:
           raise ValueError("Latitudes must be between -90 and 90 degrees")
        if lon > 180 or lon < -180:
           raise ValueError("Latitudes must be between -90 and 90 degrees")
        return values

class DataRequest(DataRequestBase, table=True):
    """
    Database model for Data Requests.

    This object contains the representation of the data in the database.
    """

    id: int | None = Field(default=None, primary_key=True)
    username: str
    title: str
    desc: str | None
    fname: str
    lname: str
    email: str
    geometry: str
    latitude: str | None
    longitude: str | None
    myFile: str | None
    start_date: datetime
    end_date: datetime
    variables: str | None
    models: str | None
    path: str
    input: str | None
    link: str | None


class DataRequestPublic(DataRequestBase):
    """
    Public model for Data Requests.

    This object contains all fields that are visible to users.
    If a field defined in DataRequests should not be visible to users, it will not
    be included in this object.
    """

    id: int
    username: str
    title: str
    desc: str | None
    fname: str
    lname: str
    email: str
    geometry: str
    latitude: str  | None
    longitude: str  | None
    myFile: str | None
    start_date: datetime
    end_date: datetime
    variables: str | None
    models: str | None
    path: str
    input: str | None
    link: str | None


class DataRequestUpdate(DataRequestBase):
    """
    Update model for Data Requests.

    This object contains all fields that are updatable on the DataRequest model.
    Fields should be optional unless they *must* be updated every time a change is made.
    """

    username: str | None = None
    title: str | None = None
    desc: str | None = None
    fname: str | None = None
    lname: str | None = None
    email: str | None = None
    geometry: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    myFile: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    variables: str | None = None
    models: str | None = None
    path: str | None = None
    input: str | None = None
    link: str | None = None