from typing import Iterable

from fastapi import FastAPI
from starlette.routing import Mount, Route


def get_routes(
    app_: FastAPI | Mount, included_in_schema_only: bool = True
) -> Iterable[dict[str, Route | Mount | FastAPI]]:
    """
    Yield a dictionary containing information about routes contained in app_.

    This includes FastAPI applications recursively mounted as well.
    If included_in_schema_only is True, do not include routes who are not included in the schema
    (ie. their included_in_schema attribute is False)._in_
    """
    for route in app_.routes:
        if isinstance(route, Mount):
            yield from get_routes(route, included_in_schema_only)
        elif route.include_in_schema or not included_in_schema_only:
            if isinstance(app_, Mount):
                yield {"route": route, "app": app_.app, "mount": app_}
            else:
                yield {"route": route, "app": app_}
