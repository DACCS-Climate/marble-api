from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import AfterValidator, BaseModel
from sqlmodel import select

from app.database import SessionDep
from app.versions.v1.models import DataRequest, DataRequestPublic, DataRequestUpdate

app = FastAPI(version="1")


@app.post("/data-publish-request")
async def post_data_request(
    data_request: Annotated[DataRequest, AfterValidator(DataRequest.model_validate)], session: SessionDep
) -> DataRequestPublic:
    """Create a new data request and return the newly created data request."""
    try:
        session.add(data_request)
        session.commit()
        session.refresh(data_request)
        return data_request
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    #session.add(data_request)
    #session.commit()
    #session.refresh(data_request)
    #return data_request


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
async def get_data_request(request_id: str, session: SessionDep) -> DataRequestPublic:
    """Get a data request with the given request_id."""
    request = session.get(DataRequest, request_id)
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
