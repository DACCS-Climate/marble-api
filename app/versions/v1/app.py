from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import AfterValidator, BaseModel
from sqlmodel import select

from app.database import SessionDep
from app.versions.v1.models import DataRequest, DataRequestPublic, DataRequestUpdate
import gbbox
from shapely.geometry import shape as shp
import json
from datetime import datetime, timezone
import pystac

app = FastAPI(version="1")


@app.post("/data-publish-request")
async def post_data_request(
    data_request: Annotated[DataRequest, AfterValidator(DataRequest.model_validate)], session: SessionDep
) -> DataRequestPublic:
    """Create a new data request and return the newly created data request."""
    session.add(data_request)
    session.commit()
    session.refresh(data_request)
    return data_request

@app.patch("/data-publish-request/{request_id}")
async def patch_data_request(
    request_id: str, data_request: DataRequestUpdate, session: SessionDep
) -> DataRequestPublic:
    """Update fields of data request and return the updated data request."""
    data_request = session.get(DataRequest, request_id)
    if not data_request:
        raise HTTPException(status_code=404, detail="data publish request not found")
    data_request.sqlmodel_update(data_request.model_dump(exclude_unset=True))
    session.add(data_request)
    session.commit()
    session.refresh(data_request)
    return data_request

@app.get("/data-publish-request/{request_id}")
async def get_data_request(request_id: str, session: SessionDep, stac: bool = False) -> DataRequestPublic:
    """Get a data request with the given request_id."""
    data_request = session.get(DataRequest, request_id)
    if stac:
        #STAC item time (creation time)
        datetime_utc = datetime.now(tz=timezone.utc)
        #Create list of custom item properties (other than geometry and time), which will be added to the STAC item
        item_properties = {
            "title": data_request.title,
            "description": data_request.desc,
            "authors_firstname": data_request.authorFNames,
            "authors_lastname": data_request.authorLNames,
            # date
            "start_datetime": data_request.start_date,
            "end_datetime": data_request.end_date,
            # variables
            "variables": data_request.variables,
            # models
            "models": data_request.models,
            "item_links": [{
                "rel": "self",
                "href": data_request.path
            },
                {
                    "rel": "derived_from",
                    "href": data_request.input
                },
                {
                    "rel": "linked_files",
                    "href": data_request.link
                }]
        }
        #generate bbox from geometry, in the case of a simple geometry where user did not provide GeoJSON geometry input
        myfile = data_request.myFile
        if data_request.myFile == "":
            latitude = json.loads(data_request.latitude)
            longitude = json.loads(data_request.longitude)
            if data_request.geometry == "Point":
                myfile = {
                    "type": "Point",
                    "coordinates": [data_request.latitude, data_request.longitude]
                    }
            if data_request.geometry == "LineString":
                myfile = {
                    "type": "LineString",
                    "coordinates": [[latitude[0], longitude[0]]]
                    }
                for i in range(1, len(latitude)):
                    myfile['coordinates'].append([latitude[i], longitude[i]])
            if data_request.geometry == "MultiPoint":
                myfile = {
                    "type": "MultiPoint",
                    "coordinates": [[data_request.latitude[0], data_request.longitude[0]]]
                    }
                for i in range(1, len(data_request.latitude)):
                    myfile['coordinates'].append([data_request.latitude[i], data_request.longitude[i]])
            if data_request.geometry == "Polygon":
                myfile = {
                    "type": "Polygon",
                    "coordinates": [[data_request.latitude[0], data_request.longitude[0]]]
                    }
                for i in range(1, len(data_request.latitude)):
                    myfile['coordinates'].append([data_request.latitude[i], data_request.longitude[i]])
        #Now that each file has a GeoJSON geometry feature (either user inputted or generated above), use gbbox package to generate gbbox
        if data_request.geometry == "Point":
            shape = gbbox.Point(**myfile)
            geobbox = shape.bbox()
        if data_request.geometry == "Line":
            geom = shp(myfile)
            geobbox = geom.bounds
        if data_request.geometry == "LineString":
            shape = gbbox.LineString(**myfile)
            geobbox = shape.bbox()
        if data_request.geometry == "MultiLineString":
            shape = gbbox.MultiLineString(**myfile)
            geobbox = shape.bbox()
        if data_request.geometry == "Polygon":
            shape = gbbox.Polygon(**myfile)
            geobbox = shape.bbox()
        if data_request.geometry == "MultiPolygon":
            shape = gbbox.MultiPolygon(**myfile)
            geobbox = shape.bbox()
        if data_request.geometry == "GeometryCollection":
            shape = gbbox.GeometryCollection(**myfile)
            geobbox = shape.bbox()           
        #Create STAC item (null case and regular case)
        if data_request.geometry == "null":
            item = pystac.Item(id=id,
                 geometry = null,
                 datetime=datetime_utc,
                 properties=item_properties)
        elif data_request.geometry != "null":
            item = pystac.Item(id=id,
                 geometry = myfile,
                 bbox = geobbox,
                 datetime=datetime_utc,
                 properties=item_properties)
        return item.to_dict() #CHECK WORKING
    if not data_request:
        raise HTTPException(status_code=404, detail="data publish request not found")
    #return request if not stac
    return data_request

class _LinksResponse(BaseModel):
    rel: str
    href: str
    type: str


class _DataRequestMultiResponse(BaseModel):
    data_publish_requests: list[DataRequestPublic]
    links: list[_LinksResponse]


@app.get("/data-publish-request")
async def get_data_requests(
    session: SessionDep,
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
) -> _DataRequestMultiResponse:
    """
    Return all data requests.

    This response is paginated and will only return at most limit objects at a time (maximum 100).
    Use the offset and limit parameters to select specific ranges of data requests.
    """
    requests = session.exec(select(DataRequest).offset(offset).limit(limit + 1)).all()
    links = []
    if len(requests) > limit:
        links.append(
            {
                "rel": "next",
                "type": "application/json",
                "href": str(request.url.replace_query_params(offset=offset + len(requests))),
            }
        )
        requests.pop()
    if offset:
        links.append(
            {
                "ref": "prev",
                "type": "application/json",
                "href": str(request.url.replace_query_params(offset=max(0, offset - limit))),
            }
        )
    return {"data_publish_requests": requests, "links": links}
