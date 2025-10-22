import inspect
import json
from urllib.parse import parse_qs, urlparse

import bson
import pytest
from stac_pydantic import Item

from marble_api.database import client
from marble_api.versions.v1.data_request.models import DataRequest, DataRequestPublic
from marble_api.versions.v1.data_request.routes import get_data_requests

pytestmark = pytest.mark.anyio


class _TestGet:
    n_data_requests = 2

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def load_data(cls, fake):
        data = [fake.data_request().model_dump() for _ in range(cls.n_data_requests)]
        await client.db.get_collection("data-request").insert_many(data)

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def cleanup(cls):
        try:
            yield
        finally:
            await client.drop_database(client.db.name)

    @pytest.fixture(scope="class")
    @classmethod
    async def data_requests(cls):
        yield await client.db.get_collection("data-request").find({}).to_list()


@pytest.mark.no_db_cleanup
class TestGetOne(_TestGet):
    async def test_get(self, async_client, data_requests):
        resp = await async_client.get(f"/v1/data-requests/{data_requests[0]['_id']}")
        assert resp.status_code == 200
        assert DataRequestPublic(**data_requests[0]) == DataRequestPublic(**resp.json())

    async def test_get_stac(self, async_client, data_requests):
        resp = await async_client.get(f"/v1/data-requests/{data_requests[0]['_id']}?stac=true")
        assert resp.status_code == 200
        assert (item := resp.json().get("stac_item"))
        Item(**item)

    async def test_bad_id(self, async_client):
        resp = await async_client.get("/v1/data-requests/id-does-not-exist")
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetMany(_TestGet):
    default_link_limit = inspect.signature(get_data_requests).parameters["limit"].default
    n_data_requests = default_link_limit + 2

    async def test_get(self, async_client, data_requests):
        response = await async_client.get("/v1/data-requests/")
        models = {str(req["_id"]): DataRequestPublic(**req) for req in data_requests}
        for req in response.json()["data_requests"]:
            assert DataRequestPublic(**req) == models[req["id"]]

    async def test_get_stac(self, async_client):
        resp = await async_client.get("/v1/data-requests/?stac=true")
        for req in resp.json()["data_requests"]:
            assert (item := req.get("stac_item"))
            Item(**item)

    async def test_get_limit_default(self, async_client):
        response = await async_client.get("/v1/data-requests/")
        assert len(response.json()["data_requests"]) == self.default_link_limit

    async def test_get_limit_non_default(self, async_client):
        response = await async_client.get("/v1/data-requests/?limit=5")
        assert len(response.json()["data_requests"]) == 5

    async def test_get_limit_more(self, async_client):
        response = await async_client.get(f"/v1/data-requests/?limit={self.n_data_requests + 1}")
        assert len(response.json()["data_requests"]) == self.n_data_requests

    async def test_get_limit_none(self, async_client):
        response = await async_client.get("/v1/data-requests/?limit=0")
        assert response.status_code == 422

    async def test_get_limit_over_max(self, async_client):
        response = await async_client.get("/v1/data-requests/?limit=200")
        assert response.status_code == 422

    async def test_get_first_page_links(self, async_client):
        response = await async_client.get("/v1/data-requests/")
        links = response.json()["links"]
        assert len(links) == 1
        link = links[0]
        assert link["rel"] == "next"
        assert link["type"] == "application/json"
        assert link["href"].startswith(str(response.url))
        assert (after_id := parse_qs(urlparse(link["href"]).query).get("after"))
        assert after_id not in [r["id"] for r in response.json()["data_requests"]]

    async def test_get_last_page_links(self, async_client):
        response = await async_client.get("/v1/data-requests/")
        next_link = next(link for link in response.json()["links"] if link["rel"] == "next")
        response2 = await async_client.get(next_link["href"])
        links = response2.json()["links"]
        assert len(links) == 1
        link = links[0]
        assert link["rel"] == "prev"
        assert link["type"] == "application/json"
        assert link["href"].startswith(str(response.url))
        assert (before_id := parse_qs(urlparse(link["href"]).query).get("before"))
        assert before_id not in [r["id"] for r in response.json()["data_requests"]]

    async def test_get_mid_page_links(self, async_client):
        response = await async_client.get("/v1/data-requests/?limit=4")
        next_link = next(link for link in response.json()["links"] if link["rel"] == "next")
        response2 = await async_client.get(next_link["href"])
        links = response2.json()["links"]
        assert len(links) == 2
        assert {link["rel"] for link in links} == {"prev", "next"}
        for link in links:
            assert link["type"] == "application/json"
            assert link["href"].startswith(str(response.url))
            assert parse_qs(urlparse(link["href"]).query).get("limit") == ["4"]
            if link["rel"] == "prev":
                assert (id_ := parse_qs(urlparse(link["href"]).query).get("before"))
            elif link["rel"] == "next":
                assert (id_ := parse_qs(urlparse(link["href"]).query).get("after"))
            assert id_ not in [r["id"] for r in response.json()["data_requests"]]


class TestPost:
    async def test_valid(self, fake, async_client):
        data = fake.data_request().model_dump_json()
        response = await async_client.post("/v1/data-requests/", json=json.loads(data))
        assert response.status_code == 200
        assert (id_ := response.json().get("id"))
        bson.ObjectId(id_)  # check that the id is a valid object id
        assert json.loads(data) == json.loads(DataRequest(**response.json()).model_dump_json())

    async def test_invalid(self, fake, async_client):
        data = json.loads(fake.data_request().model_dump_json())
        data["authors"] = []
        response = await async_client.post("/v1/data-requests/", json=data)
        assert response.status_code == 422


class _TestUpdate:
    @pytest.fixture
    async def loaded_data(self, fake):
        model = json.loads(fake.data_request().model_dump_json())
        resp = await client.db.get_collection("data-request").insert_one(model)
        model.pop("_id")
        model["id"] = str(resp.inserted_id)
        return model


class TestPatch(_TestUpdate):
    async def test_valid(self, loaded_data, async_client, fake):
        title = fake.sentence()
        update = {"title": title}
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        assert loaded_data == response.json()

    async def test_valid_multiple(self, loaded_data, async_client, fake):
        title = fake.sentence()
        authors = [fake.author(), fake.author()]
        update = {"title": title, "authors": authors}
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        assert loaded_data == response.json()

    async def test_update_nothing(self, loaded_data, async_client):
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json={})
        assert response.status_code == 200
        assert loaded_data == response.json()

    async def test_update_everything(self, loaded_data, async_client, fake):
        update = json.loads(fake.data_request().model_dump_json())
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json=update)
        assert response.status_code == 200
        update["id"] = loaded_data["id"]
        assert update == response.json()

    async def test_no_id_update(self, loaded_data, async_client):
        update = {"id": str(bson.ObjectId())}
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json=update)
        assert response.status_code == 200
        assert response.json()["id"] == loaded_data["id"]
        assert response.json()["id"] != update["id"]
        assert loaded_data == response.json()

    async def test_invalid_unset_value(self, loaded_data, async_client):
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json={"title": None})
        assert response.status_code == 422

    async def test_invalid_bad_type(self, loaded_data, async_client):
        response = await async_client.patch(f"/v1/data-requests/{loaded_data['id']}", json={"title": 10})
        assert response.status_code == 422

    async def test_bad_id(self, async_client):
        resp = await async_client.patch("/v1/data-requests/id-does-not-exist", json={})
        assert resp.status_code == 404, resp.json()


class TestDelete(_TestUpdate):
    async def test_exists(self, loaded_data, async_client):
        response = await async_client.delete(f"/v1/data-requests/{loaded_data['id']}")
        assert response.status_code == 204
        resp = await client.db.get_collection("data-request").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is None

    async def test_bad_id(self, async_client):
        resp = await async_client.delete("/v1/data-requests/id-does-not-exist")
        assert resp.status_code == 404, resp.json()
