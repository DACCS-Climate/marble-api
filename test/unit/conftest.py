from unittest.mock import MagicMock

import pytest

from marble_api.database import client


@pytest.fixture(autouse=True)
def mock_db():
    mock = MagicMock()
    client.get_default_database = mock
    return mock
