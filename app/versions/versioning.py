from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.utils import get_routes

if TYPE_CHECKING:
    from typing import Callable, Iterable


def _get_app_methods(app_: FastAPI) -> "Iterable[tuple[str, str]]":
    for info in get_routes(app_):
        route = info["route"]
        for method in route.methods:
            yield (method, route.path)


def add_fallback_routes(app_: FastAPI, previous_version: FastAPI) -> None:
    """Add routes from a previous version to app_."""
    current_routes = set(_get_app_methods(app_))
    for info in get_routes(previous_version):
        route = info["route"]
        previous_routes = {(method, route.path) for method in route.methods}
        if (
            info.get("mount") is None
            and not getattr(route.endpoint, "_last_version", False)
            and not previous_routes & current_routes
        ):
            app_.router.routes.append(route)


def last_version() -> "Callable":
    """Indicate that the decorated route should not be included in subsequent versions."""

    def _(func: "Callable") -> "Callable":
        func._last_version = True
        return func

    return _
