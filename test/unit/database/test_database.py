from marble_api.database import Client, client, collection


class TestClient:
    def test_default_database(self):
        assert Client("mongodb://example.com").get_default_database().name == "marble-api"

    def test_default_database_from_uri(self):
        assert Client("mongodb://example.com/other-db").get_default_database().name == "other-db"

    def test_db(self):
        assert Client("mongodb://example.com").db.name == "marble-api"

    def test_db_from_uri(self):
        assert Client("mongodb://example.com/other-db").db.name == "other-db"


def test_collection():
    collection("test")


class TestCollection:
    def test_collection_call(self):
        collection("test")()
        args_list = client.db.__getitem__.call_args_list
        assert len(args_list) == 1
        assert args_list[0].args == ("test",)

    def test_collection_call_override(self):
        collection("test")("test2")
        args_list = client.db.__getitem__.call_args_list
        assert len(args_list) == 1
        assert args_list[0].args == ("test2",)


def test_client_singleton():
    assert isinstance(client, Client)
