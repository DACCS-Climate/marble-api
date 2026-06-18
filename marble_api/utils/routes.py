from typing import Any

import pymongo
from bson import ObjectId
from fastapi import Request
from pymongo.asynchronous.collection import AsyncCollection
from stac_pydantic.links import Links


async def paginated_query(
    collection: AsyncCollection,
    limit: int,
    request: Request,
    sort_by: str = "_id",
    after: ObjectId | None = None,
    before: ObjectId | None = None,
    ascending: bool = True,
    **selector,
) -> tuple[list[dict[str, Any]], Links]:
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
