import os

# set this to false by default so that tests don't require magpie authentication
# unless explicitly set during the tests
os.environ["MARBLE_API_MAGPIE_AUTH_ENABLED"] = "false"

import pytest
from faker_providers import DataRequestProvider, GeoJsonProvider

from marble_api._config import config


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def faker_providers():
    return {"DataRequestProvider": DataRequestProvider, "GeoJsonProvider": GeoJsonProvider}


@pytest.fixture
def test_config():
    prev = config.model_dump()
    try:
        yield config
    finally:
        for k, v in prev.items():
            setattr(config, k, v)
