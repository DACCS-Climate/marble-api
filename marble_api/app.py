from importlib import metadata

from fastapi import FastAPI, Request

from marble_api.versions.v1.app import router as v1_router

_metadata = metadata.metadata("marble_api").json

app = FastAPI(
    title=_metadata["name"],
    version=_metadata["version"],
    description=_metadata["summary"],
    docs_url=None,
    redoc_url="/docs",
)

app.include_router(v1_router)


@app.get("/", tags=["root"])
async def root(request: Request) -> dict:
    """Return app information."""
    return {"name": request.app.title, "version": request.app.version, "description": request.app.description}


_original_openapi = app.openapi


def openapi_with_tag_groups() -> dict:
    """Update openapi schema with x-tagGroup data for nested versions."""
    if app.openapi_schema:
        return app.openapi_schema

    _original_openapi()
    groups = {"/": {"root"}}
    for path, path_schema in app.openapi_schema["paths"].items():
        path_version = path.split("/")[1]
        if path_version.startswith("v"):
            version_tag = f"Version {path_version[1:]}"
            if version_tag not in groups:
                groups[version_tag] = set()
            for route_schema in path_schema.values():
                if "tags" in route_schema:
                    route_schema["tags"] = [f"{path_version}: {tag}" for tag in route_schema["tags"]]
                    groups[version_tag].update(route_schema["tags"])
    app.openapi_schema["x-tagGroups"] = [{"name": group, "tags": list(tags)} for group, tags in groups.items()]
    return app.openapi_schema


app.openapi = openapi_with_tag_groups
