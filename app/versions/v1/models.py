from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class DataRequestBase(SQLModel):
    """
    SQL model base object for Data Requests.

    This object contains field validators.
    """

    @field_validator("start_date","end_date", check_fields=False)
    def validate_timeperiod(cls, start_date: datetime, end_date: datetime) -> datetime:
        """Check that the time periods are correct"""
        if end_date < start_date:
            raise ValueError("End date can not be earlier than start date")
        return start_date, end_date
    
    @field_validator("longitude", "latitude", "myFile", check_fields=False)
    def validate_title(cls, latitude: str, longitude: str, myFile:str) -> str:
        """Ensure list lengths match"""
        if len(latitude) != len(longitude):
            raise ValueError("Latitude and longitude lists are different lengths")
        """If there is no latitude and longitude, make sure there is a GeoJSON"""
        if latitude == None:
            if myFile == None:
                raise ValueError("Must include either GeoJSON file or manually inputted latitude and longitudes")
        """Check latitude and longitude ranges"""
        for i in latitude:
            if i > 90:
                raise ValueError("Latitudes must be between -90 and 90 degrees")
            if i < -90: 
                raise ValueError("Latitudes must be between -90 and 90 degrees")
        for i in longitude:
            if i > 180:
                raise ValueError("Longitudes must be between -180 and 180 degrees")
            if i < -180: 
                raise ValueError("Longitudes must be between -180 and 180 degrees") 
        
        return latitude, longitude, myFile


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

    id: int | None = Field(default=None, primary_key=True)
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
