import pytest

from marble_api.app import VERSIONS

pytestmark = [pytest.mark.anyio, pytest.mark.no_db_cleanup]


async def test_root_in_root(async_client):
    resp = await async_client.get("/")
    assert {"methods": ["GET"], "path": "/"} in resp.json()["routes"]


async def test_version_roots_in_root(async_client):
    resp = await async_client.get("/")
    for version, _ in VERSIONS:
        assert {"methods": ["GET"], "path": f"{version}/"} in resp.json()["routes"]
