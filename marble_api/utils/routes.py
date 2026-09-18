import datetime
from typing import Annotated, Any, TypedDict

import pymongo
from bson import ObjectId
from fastapi import HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from pymongo.asynchronous.collection import AsyncCollection
from stac_pydantic.links import Links

from marble_api.database import client
from marble_api.utils.models import MarbleBaseModel

type MongoRecord = dict[str, Any]


async def _paginated_query(
    collection: AsyncCollection,
    limit: int,
    request: Request,
    sort_by: str = "_id",
    after: ObjectId | None = None,
    before: ObjectId | None = None,
    ascending: bool = True,
    **selector,
) -> tuple[list[MongoRecord], Links]:
    """Return the result of a paginated query."""
    reverse_it = False
    sort_order = pymongo.ASCENDING if ascending else pymongo.DESCENDING
    if after or before:
        if after:
            comparator = "$gt" if ascending else "$lt"
            last_id = after
        else:
            comparator = "$lt" if ascending else "$gt"
            sort_order *= -1
            last_id = before
            reverse_it = True  # put the eventual result back in the requested order for consistency
        if sort_by == "id":
            selector["_id"] = {comparator: last_id}
        else:
            last_sort_value = (await collection.find_one({"_id": last_id})).get(sort_by)
            selector["$or"] = [
                {sort_by: {comparator: last_sort_value}},
                {sort_by: last_sort_value, "_id": {comparator: last_id}},
            ]
    db_request = collection.find(selector).sort([(sort_by, sort_order), ("_id", sort_order)])

    data = await db_request.limit(limit + 1).to_list()
    if reverse_it:
        data = list(reversed(data))

    query_params = {}

    over_limit = len(data) > limit

    if data:
        if after:
            if over_limit:
                data.pop()
                query_params["after"] = data[-1]["_id"]
            query_params["before"] = data[0]["_id"]
        elif before:
            if over_limit:
                data.pop(0)
                query_params["before"] = data[0]["_id"]
            query_params["after"] = data[-1]["_id"]
        elif over_limit:
            data.pop()
            query_params["after"] = data[-1]["_id"]

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
    return data, links


def _build_selector(
    id_: ObjectId | None, user: str | None, additional_selector: dict[str, Any] | None
) -> dict[str, Any]:
    selector = additional_selector or {}
    if id_ is not None:
        selector["_id"] = id_
    if user is not None:
        selector["user"] = user
    return selector


async def post_record(collection: AsyncCollection, user: str | None, model: MarbleBaseModel) -> MongoRecord:
    """Create a record in the database collection based on the given model and return the created model."""
    if user is not None:
        model.user = user
    model.updated = datetime.datetime.now(tz=datetime.timezone.utc)
    new_model = model.model_dump(by_alias=True)
    result = await collection.insert_one(new_model)
    new_model["id"] = str(result.inserted_id)
    return new_model


async def patch_record(
    collection: AsyncCollection,
    id_: ObjectId | None,
    user: str | None,
    data: Any,  # not MarbleBaseModelUpdate because patch can operate on individual fields  # noqa: ANN401
    validation_class: MarbleBaseModel,
    allow_update_user: bool = False,
    additional_selector: dict[str, Any] | None = None,
    set_prefix: str | None = None,
) -> MongoRecord:
    """Update fields of a record in the database collection and return the updated record."""
    if isinstance(data, BaseModel):
        updated_fields = data.model_dump(exclude_unset=True, by_alias=True)
    else:
        updated_fields = data  # allows updating partial records that are not defined by a pydantic model
    if set_prefix is not None:
        updated_fields = {f"{set_prefix}{field}": value for field, value in updated_fields.items()}
    selector = _build_selector(id_, user, additional_selector)
    if not allow_update_user and "user" in updated_fields:
        # do not allow updating user field
        raise HTTPException(status_code=403, detail="Forbidden")
    # updated timestamps are handled automatically
    if updated_fields:
        updated_fields["updated"] = datetime.datetime.now(tz=datetime.timezone.utc)
        async with client.start_session() as session:
            async with await session.start_transaction():
                result = await collection.find_one_and_update(
                    selector, {"$set": updated_fields}, return_document=pymongo.ReturnDocument.AFTER
                )
                if result is not None:
                    validation_class(**result)
                    return result
    else:
        if (result := await collection.find_one(selector)) is not None:
            return result

    raise HTTPException(status_code=404, detail="Not found")


async def get_record(
    collection: AsyncCollection,
    id_: ObjectId | None,
    user: str | None,
    additional_selector: dict[str, Any] | None = None,
) -> MongoRecord:
    """Get a record from the database collection with the given id."""
    selector = _build_selector(id_, user, additional_selector)
    if (result := await collection.find_one(selector)) is not None:
        return result

    raise HTTPException(status_code=404, detail="Not found")


class RecordsResponse(TypedDict):
    """Describes the return value for the get_records function."""

    records: list[MongoRecord]
    links: Links


async def get_records(
    collection: AsyncCollection,
    request: Request,
    user: str | None = None,
    after: ObjectId | None = None,
    before: ObjectId | None = None,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
    sort_by: str = "id",
    ascending: bool = True,
    additional_selector: dict[str, Any] | None = None,
    records_key: str = "records",
) -> RecordsResponse:
    """Get records from the database collection, paginated according to the after, before, sort_by, and ascending params."""
    # note: created is not a field, it is based on the timesamp used to create the value of _id
    if sort_by in ("id", "created"):
        sort_by = "_id"

    selector = _build_selector(None, user, additional_selector)

    records, links = await _paginated_query(
        collection=collection,
        limit=limit,
        request=request,
        sort_by=sort_by,
        after=after,
        before=before,
        ascending=ascending,
        **selector,
    )
    return {records_key: records, "links": links}


async def delete_record(
    collection: AsyncCollection,
    id_: ObjectId | None,
    user: str | None,
    additional_selector: dict[str, Any] | None = None,
) -> Response:
    """Delete a data request from the database collection with the given id."""
    selector = _build_selector(id_, user, additional_selector)

    result = await collection.delete_one(selector)
    if result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail="Not found")
