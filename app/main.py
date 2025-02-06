from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

from app.database import on_start
from app.utils import get_routes
from app.versions.v1.app import app as v1_app
from app.versions.versioning import add_fallback_routes

VERSIONS = [("/v1", v1_app)]

if TYPE_CHECKING:
    from typing import AsyncIterable


@asynccontextmanager
async def lifespan(app: FastAPI) -> "AsyncIterable":
    """Execute setup/teardown code around when the app starts/stops."""
    on_start()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root(request: Request) -> dict:
    """Return information about all routes."""
    return {
        "routes": [
            {
                "path": f"{m.path if (m := info.get('mount')) else ''}{info['route'].path}",
                "methods": info["route"].methods,
            }
            for info in get_routes(request.app, included_in_schema_only=True)
        ]
    }


def _mount_versions() -> None:
    """Mount all implemented versions of this API under app."""
    for i, (prefix, version_app) in enumerate(VERSIONS):
        app.mount(prefix, version_app)
        previous_version = VERSIONS[i - 1][1] if i else app
        add_fallback_routes(version_app, previous_version)


_mount_versions()
