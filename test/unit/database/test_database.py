from marble_api.database import Client, client


class TestClient:
    def test_default_database(self):
        assert Client("mongodb://example.com").get_default_database().name == "marble-api"

    def test_default_database_from_uri(self):
        assert Client("mongodb://example.com/other-db").get_default_database().name == "other-db"

    def test_db(self):
        assert Client("mongodb://example.com").db.name == "marble-api"

    def test_db_from_uri(self):
        assert Client("mongodb://example.com/other-db").db.name == "other-db"


def test_client_singleton():
    assert isinstance(client, Client)
