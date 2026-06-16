import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.no_db_cleanup]


async def test_root_in_root(async_client):
    resp = await async_client.get("/")
    assert "name" in resp.json()
    assert "version" in resp.json()
    assert "description" in resp.json()
