import functools

import pytest
from httpx import ASGITransport, AsyncClient

from marble_api import app
from marble_api.database import client


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    # use different default database name from prod/dev in order to minimize the chance
    # of accidentally using a prod/dev database.
    client.get_default_database = functools.partial(client.get_default_database, default="marble-api-test")


@pytest.fixture(scope="session", autouse=True)
async def check_empty_test_db(init_test_db):
    database = client.db
    if await database.list_collection_names():
        raise RuntimeError(
            f"Database {database.name} contains some collections. Tests must be run on an empty database."
        )


@pytest.fixture(autouse=True)
async def refresh_database(request):
    try:
        yield
    finally:
        if "no_db_cleanup" not in request.keywords:
            await client.drop_database(client.db.name)


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
