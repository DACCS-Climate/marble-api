from typing import Annotated

import pymongo
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pymongo import ReturnDocument

from marble_api.database import client
from marble_api.utils.models import object_id
from marble_api.versions.v1.data_request.models import (
    DataRequest,
    DataRequestPublic,
    DataRequestsResponse,
    DataRequestUpdate,
)

router = APIRouter(prefix="/data-requests")


def _data_request_id(id_: str) -> ObjectId:
    return object_id(id_, HTTPException(status_code=404, detail=f"data publish request with id={id_} not found"))


@router.post("/")
async def post_data_request(data_request: DataRequest) -> DataRequestPublic:
    """Create a new data request and return the newly created data request."""
    new_data_request = data_request.model_dump(by_alias=True)
    result = await client.db["data-request"].insert_one(new_data_request)
    new_data_request["id"] = result.inserted_id
    return new_data_request


@router.patch("/{request_id}")
async def patch_data_request(request_id: str, data_request: DataRequestUpdate) -> DataRequestPublic:
    """Update fields of data request and return the updated data request."""
    updated_fields = data_request.model_dump(exclude_unset=True, by_alias=True)
    selector = {"_id": _data_request_id(request_id)}
    if updated_fields:
        updated_fields.update(data_request.model_dump(include="stac_item"))
        result = await client.db["data-request"].find_one_and_update(
            selector, {"$set": updated_fields}, return_document=ReturnDocument.AFTER
        )
        if result is not None:
            return result
    else:
        if (result := await client.db["data-request"].find_one(selector)) is not None:
            return result

    raise HTTPException(status_code=404, detail="data publish request not found")


@router.get("/{request_id}", response_model_by_alias=False)
async def get_data_request(request_id: str, stac: bool = False) -> DataRequestPublic:
    """Get a data request with the given request_id."""
    if (result := await client.db["data-request"].find_one({"_id": _data_request_id(request_id)})) is not None:
        if stac:
            try:
                result["stac_item"] = DataRequestPublic(**result).stac_item
            except Exception as e:
                raise Exception(result) from e
        return result

    raise HTTPException(status_code=404, detail="data publish request not found")


@router.delete("/{request_id}")
async def delete_data_request(request_id: str) -> Response:
    """Delete a data request with the given request_id."""
    result = await client.db["data-request"].delete_one({"_id": _data_request_id(request_id)})

    if result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail="data publish request not found")


@router.get("/")
async def get_data_requests(
    request: Request,
    after: str | None = None,
    before: str | None = None,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
    stac: bool = False,
) -> DataRequestsResponse:
    """
    Return all data requests.

    This response is paginated and will only return at most limit objects at a time (maximum 100).
    Use the offset and limit parameters to select specific ranges of data requests.
    """
    reverse_it = False
    if after:
        db_request = (
            client.db["data-request"].find({"_id": {"$gte": _data_request_id(after)}}).sort("_id", pymongo.ASCENDING)
        )
    elif before:
        db_request = (
            client.db["data-request"].find({"_id": {"$lte": _data_request_id(before)}}).sort("_id", pymongo.DESCENDING)
        )
        reverse_it = True  # put the eventual result back in ascending order for consistency
    else:
        db_request = client.db["data-request"].find({}).sort("_id", pymongo.ASCENDING)

    data_requests = await db_request.limit(limit + 1).to_list()
    if reverse_it:
        data_requests = reversed(data_requests)

    query_params = {}

    over_limit = len(data_requests) > limit

    if data_requests:
        if after:
            if over_limit:
                query_params["after"] = data_requests[-1]["_id"]
            query_params["before"] = data_requests.pop(0)["_id"]
        elif before:
            if over_limit:
                query_params["before"] = data_requests[0]["_id"]
            query_params["after"] = data_requests.pop()["_id"]
        elif over_limit:
            query_params["after"] = data_requests.pop()["_id"]

    links = []

    base_url = request.url.remove_query_params(["after", "before"])
    if query_params.get("after"):
        links.append(
            {
                "rel": "next",
                "type": "application/json",
                "href": str(base_url.include_query_params(after=query_params["after"])),
            }
        )
    if query_params.get("before"):
        links.append(
            {
                "rel": "prev",
                "type": "application/json",
                "href": str(base_url.include_query_params(before=query_params["before"])),
            }
        )
    if stac:
        data_requests = [{**r, "stac_item": DataRequestPublic(**r).stac_item} for r in data_requests]
    return {"data_requests": data_requests, "links": links}
