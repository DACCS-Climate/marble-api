import datetime
from collections.abc import AsyncGenerator
from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic_core import PydanticSerializationError
from pymongo import ReturnDocument

from marble_api.database import client
from marble_api.utils.models import object_id
from marble_api.utils.routes import paginated_query
from marble_api.versions.v1.data_request.models import (
    DataRequest,
    DataRequestPublic,
    DataRequestsResponse,
    DataRequestUpdate,
)


async def _handle_serialization_error() -> AsyncGenerator[None]:
    try:
        yield
    except PydanticSerializationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


user_router = APIRouter(prefix="/data-requests")
admin_router = APIRouter(prefix="/data-requests", dependencies=[Depends(_handle_serialization_error)])


def _data_request_id(id_: str) -> ObjectId:
    return object_id(id_, HTTPException(status_code=404, detail=f"data publish request with id={id_} not found"))


@user_router.post("/")
@admin_router.post("/")
async def post_data_request_user(user: str, data_request: DataRequest) -> DataRequestPublic:
    """Create a new data request and return the newly created data request."""
    data_request.user = user
    data_request.updated = datetime.datetime.now(tz=datetime.timezone.utc)
    new_data_request = data_request.model_dump(by_alias=True)
    result = await client.db["data-request"].insert_one(new_data_request)
    new_data_request["id"] = str(result.inserted_id)
    return new_data_request


def _check_user_change(data_request: DataRequestUpdate, user: str | None = None) -> None:
    """Users cannot change the data request so that it belongs to a different user."""
    updated_fields = data_request.model_dump(exclude_unset=True, by_alias=True)
    if updated_fields.get("user") and user != updated_fields.get("user"):
        raise HTTPException(status_code=403, detail="Forbidden")


@user_router.patch("/{request_id}", dependencies=[Depends(_check_user_change)])
@admin_router.patch("/{request_id}")
async def patch_data_request(
    request_id: str, data_request: DataRequestUpdate, user: str | None = None
) -> DataRequestPublic:
    """Update fields of data request and return the updated data request."""
    updated_fields = data_request.model_dump(exclude_unset=True, by_alias=True)
    if user is not None:
        data_request.user = user
    selector = {"_id": _data_request_id(request_id)}
    # updated timestamps are handled automatically
    updated_fields["updated"] = datetime.datetime.now(tz=datetime.timezone.utc)
    if updated_fields:
        result = await client.db["data-request"].find_one_and_update(
            selector, {"$set": updated_fields}, return_document=ReturnDocument.AFTER
        )
        if result is not None:
            return result
    else:
        if (result := await client.db["data-request"].find_one(selector)) is not None:
            return result

    raise HTTPException(status_code=404, detail="data publish request not found")


@user_router.get("/{request_id}", response_model_by_alias=False)
@admin_router.get("/{request_id}", response_model_by_alias=False)
async def get_data_request(request_id: str, stac: bool = False, user: str | None = None) -> DataRequestPublic:
    """Get a data request with the given request_id."""
    selector = {"_id": _data_request_id(request_id)}
    if user is not None:
        selector["user"] = user
    if (result := await client.db["data-request"].find_one(selector)) is not None:
        if stac:
            try:
                result["stac_item"] = DataRequestPublic(**result).stac_item
            except Exception as e:
                raise Exception(result) from e
        return result

    raise HTTPException(status_code=404, detail="data publish request not found")


@user_router.delete("/{request_id}")
@admin_router.delete("/{request_id}")
async def delete_data_request(request_id: str, request: Request, user: str | None = None) -> Response:
    """Delete a data request with the given request_id."""
    selector = {"_id": _data_request_id(request_id)}
    if user is not None:
        selector["user"] = user

    result = await client.db["data-request"].delete_one(selector)
    if result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail="data publish request not found")


@user_router.get("/")
@admin_router.get("/")
async def get_data_requests(
    request: Request,
    user: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
    sort_by: Literal["id", "user", "contact", "title", "created", "updated"] = "id",
    ascending: bool = True,
    stac: bool = False,
) -> DataRequestsResponse:
    """
    Return all data requests.

    This response is paginated and will only return at most limit objects at a time (maximum 100).
    Use the offset and limit parameters to select specific ranges of data requests.
    """
    # note: created is not a field, it is based on the timesamp used to create the value of _id
    if sort_by in ("id", "created"):
        sort_by = "_id"

    selector = {}

    if user is not None:
        selector["user"] = user

    data_requests, links = await paginated_query(
        collection=client.db["data-request"],
        limit=limit,
        request=request,
        sort_by=sort_by,
        after=_data_request_id(after) if after else None,
        before=_data_request_id(before) if before else None,
        ascending=ascending,
        **selector,
    )

    if stac:
        data_requests = [{**r, "stac_item": DataRequestPublic(**r).stac_item} for r in data_requests]
    return {"data_requests": data_requests, "links": links}
