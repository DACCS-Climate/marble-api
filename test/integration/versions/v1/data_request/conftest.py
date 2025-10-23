import pytest
from faker import Faker


@pytest.fixture(scope="session")
def fake(faker_providers):
    fake_ = Faker()
    fake_.add_provider(faker_providers["DataRequestProvider"])
    return fake_
