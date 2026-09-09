from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request, Response

from marble_api.database import collection
from marble_api.utils.models import object_id
from marble_api.utils.routes import delete_record, get_record, get_records, patch_record, post_record
from marble_api.versions.v1.data_request.models import (
    DataRequest,
    DataRequestPublic,
    DataRequestsResponse,
    DataRequestUpdate,
)

user_router = APIRouter(prefix="/data-requests")
admin_router = APIRouter(prefix="/data-requests")


def _data_request_id(id_: str) -> ObjectId:
    return object_id(id_, HTTPException(status_code=404, detail=f"data publish request with id={id_} not found"))


_collection = collection("data-request")


@user_router.post("/")
@admin_router.post("/")
async def post_data_request_user(user: str, data_request: DataRequest) -> DataRequestPublic:
    """Create a new data request and return the newly created data request."""
    return await post_record(_collection(), user, data_request)


@user_router.patch("/{request_id}")
@admin_router.patch("/{request_id}")
async def patch_data_request(
    request_id: str, data_request: DataRequestUpdate, user: str | None = None
) -> DataRequestPublic:
    """Update fields of data request and return the updated data request."""
    return await patch_record(
        _collection(),
        _data_request_id(request_id),
        user,
        data_request,
        DataRequestPublic,
        allow_update_user=user is None,
    )


@user_router.get("/{request_id}", response_model_by_alias=False)
@admin_router.get("/{request_id}", response_model_by_alias=False)
async def get_data_request(request_id: str, stac: bool = False, user: str | None = None) -> DataRequestPublic:
    """Get a data request with the given request_id."""
    result = await get_record(_collection(), _data_request_id(request_id), user)
    if stac:
        try:
            result["stac_item"] = DataRequestPublic(**result).stac_item
        except Exception as e:
            raise Exception(result) from e
    return result


@user_router.delete("/{request_id}")
@admin_router.delete("/{request_id}")
async def delete_data_request(request_id: str, user: str | None = None) -> Response:
    """Delete a data request with the given request_id."""
    return await delete_record(_collection(), _data_request_id(request_id), user)


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
    response = await get_records(
        collection=_collection(),
        request=request,
        user=user,
        after=_data_request_id(after) if after else None,
        before=_data_request_id(before) if before else None,
        limit=limit,
        sort_by=sort_by,
        ascending=ascending,
        records_key="data_requests",
    )
    if stac:
        response["data_requests"] = [
            {**r, "stac_item": DataRequestPublic(**r).stac_item} for r in response["data_requests"]
        ]
    return response
