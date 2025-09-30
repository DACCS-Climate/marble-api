import pytest
from faker_providers import DataRequestProvider, GeoJsonProvider


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def faker_providers():
    return {"DataRequestProvider": DataRequestProvider, "GeoJsonProvider": GeoJsonProvider}
