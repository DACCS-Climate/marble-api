from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import AfterValidator, BaseModel
from sqlmodel import select

from app.database import SessionDep
from app.versions.v1.models import DataRequest, DataRequestPublic, DataRequestUpdate
import geojson as gj

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
    request = session.get(DataRequest, request_id)
    if stac:
        request = {
        #generate footprint and bbox from geometry
        #STAC item time (creation time)
        datetime_utc = datetime.now(tz=timezone.utc)
        #code to convert to a STAC item
        item = pystac.Item(id=id,
                 geometry=myfile,
                 bbox= gj.bbox_get(myfile),
                 datetime=datetime_utc,
                 properties={})
        item_properties = {
            "title": title,
            "description": desc,
            "authors_firstname": authorFNames,
            "authors_lastname": authorLNames,
            # date
            "start_datetime": start_date,
            "end_datetime": end_date,
            "created": fdict["date"],
            # variables
            "variables": variables,
            # models
            "models": models,
            "item_links": [{
                "rel": "self",
                "href": path
            },
                {
                    "rel": "derived_from",
                    "href": input
                },
                {
                    "rel": "linked_files",
                    "href": link
                }]
        }
        }
    if not request:
        raise HTTPException(status_code=404, detail="data publish request not found")
    return request


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
