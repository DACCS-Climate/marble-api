import inspect
import json
from urllib.parse import parse_qs, urlparse

import bson
import pytest
from stac_pydantic import Item

from marble_api.database import client
from marble_api.versions.v1.data_request.models import DataRequestPublic
from marble_api.versions.v1.data_request.routes import get_data_requests

pytestmark = pytest.mark.anyio


class _TestUser:
    @pytest.fixture
    def member_route(self, data_requests):
        return f"/v1/users/{data_requests[0]['user']}/data-requests/{data_requests[0]['_id']}"

    @pytest.fixture
    def collection_route(self, data_requests):
        return f"/v1/users/{data_requests[0]['user']}/data-requests/"


class _TestAdmin:
    @pytest.fixture
    def member_route(self, data_requests):
        return f"/v1/admin/data-requests/{data_requests[0]['_id']}"

    @pytest.fixture
    def collection_route(self):
        return "/v1/admin/data-requests/"


class _TestGet:
    n_data_requests = 2

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def load_data(cls, fake):
        data = [fake.data_request(user="user1").model_dump() for _ in range(cls.n_data_requests // 2)] + [
            fake.data_request(user="user2").model_dump() for _ in range(cls.n_data_requests - cls.n_data_requests // 2)
        ]
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


class _TestGetOne(_TestGet):
    async def test_get(self, async_client, data_requests, member_route):
        resp = await async_client.get(member_route)
        assert resp.status_code == 200
        assert DataRequestPublic(**data_requests[0]) == DataRequestPublic(**resp.json())

    async def test_get_stac(self, async_client, member_route):
        resp = await async_client.get(f"{member_route}?stac=true")
        assert resp.status_code == 200
        assert (item := resp.json().get("stac_item"))
        Item(**item)

    async def test_bad_id(self, async_client, member_route):
        invalid_route = "/".join(member_route.split("/")[:-1] + ["some-bad-id"])
        resp = await async_client.get(invalid_route)
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetOneUser(_TestGetOne, _TestUser):
    async def test_bad_user(self, async_client, data_requests):
        invalid_route = f"/v1/users/{data_requests[0]['user'] + '-bad-user'}/data-requests/{data_requests[0]['_id']}"
        resp = await async_client.get(invalid_route)
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetOneAdmin(_TestGetOne, _TestAdmin): ...


class _TestGetMany(_TestGet):
    default_link_limit = inspect.signature(get_data_requests).parameters["limit"].default
    n_data_requests = default_link_limit * 2 + 2
    n_data_requests_return_count: int

    async def test_get(self, async_client, data_requests, collection_route):
        response = await async_client.get(collection_route)
        models = {str(req["_id"]): DataRequestPublic(**req) for req in data_requests}
        for req in response.json()["data_requests"]:
            assert DataRequestPublic(**req) == models[req["id"]]

    async def test_get_stac(self, async_client, collection_route):
        resp = await async_client.get(f"{collection_route}?stac=true")
        for req in resp.json()["data_requests"]:
            assert (item := req.get("stac_item"))
            Item(**item)

    async def test_get_limit_default(self, async_client, collection_route):
        response = await async_client.get(collection_route)
        assert len(response.json()["data_requests"]) == self.default_link_limit

    async def test_get_limit_non_default(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit=5")
        assert len(response.json()["data_requests"]) == 5

    async def test_get_limit_more(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit={self.n_data_requests + 1}")
        assert len(response.json()["data_requests"]) == self.n_data_requests_return_count

    async def test_get_limit_none(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit=0")
        assert response.status_code == 422

    async def test_get_limit_over_max(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit=200")
        assert response.status_code == 422

    async def test_get_first_page_links(self, async_client, collection_route):
        response = await async_client.get(collection_route)
        links = response.json()["links"]
        assert len(links) == 1
        link = links[0]
        assert link["rel"] == "next"
        assert link["type"] == "application/json"
        assert link["href"].startswith(str(response.url))
        assert (after_id := parse_qs(urlparse(link["href"]).query).get("after"))
        assert after_id not in [r["id"] for r in response.json()["data_requests"]]

    async def test_get_last_page_links(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit={self.n_data_requests_return_count - 3}")
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

    async def test_get_mid_page_links(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit=4")
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

    async def test_next_prev_is_consistent(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit=4")
        # page0 -> page1
        next_link = next(link for link in response.json()["links"] if link["rel"] == "next")
        next_response = await async_client.get(next_link["href"])
        # page0 -> page1 -> page2
        next_next_link = next(link for link in next_response.json()["links"] if link["rel"] == "next")
        next_next_response = await async_client.get(next_next_link["href"])
        # page0 -> page1 -> page0
        next_prev_link = next(link for link in next_response.json()["links"] if link["rel"] == "prev")
        next_prev_response = await async_client.get(next_prev_link["href"])
        # page0 -> page1 -> page2 -> page1
        next_next_prev_link = next(link for link in next_next_response.json()["links"] if link["rel"] == "prev")
        next_next_prev_response = await async_client.get(next_next_prev_link["href"])
        # page0 -> page1 -> page2 -> page1 -> page0
        next_next_prev_prev_link = next(
            link for link in next_next_prev_response.json()["links"] if link["rel"] == "prev"
        )
        next_next_prev_prev_response = await async_client.get(next_next_prev_prev_link["href"])
        assert response.json() == next_prev_response.json() == next_next_prev_prev_response.json()
        assert next_response.json() == next_next_prev_response.json()

    async def test_get_all_same_as_paging_next(self, async_client, collection_route):
        all_response = await async_client.get(f"{collection_route}?limit={self.n_data_requests}")
        next_link = [f"{collection_route}?limit=4"]
        data_requests = []
        while next_link:
            response = await async_client.get(next_link[0])
            data_requests.extend(response.json()["data_requests"])
            next_link = [link["href"] for link in response.json()["links"] if link["rel"] == "next"]
        assert all_response.json()["data_requests"] == data_requests


@pytest.mark.no_db_cleanup
class TestGetManyUser(_TestGetMany, _TestUser):
    n_data_requests_return_count = _TestGetMany.n_data_requests // 2

    async def test_get_all(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit={self.n_data_requests}")
        assert len(response.json()["data_requests"]) == self.n_data_requests // 2


@pytest.mark.no_db_cleanup
class TestGetManyAdmin(_TestGetMany, _TestAdmin):
    n_data_requests_return_count = _TestGetMany.n_data_requests

    async def test_get_all(self, async_client, collection_route):
        response = await async_client.get(f"{collection_route}?limit={self.n_data_requests}")
        assert len(response.json()["data_requests"]) == self.n_data_requests


class _TestPost:
    @pytest.fixture
    def data_requests(self):
        return [{"user": "user1"}]

    async def test_valid(self, fake, async_client, collection_route, data_requests):
        data = fake.data_request().model_dump_json(exclude=["user"])
        response = await async_client.post(collection_route, json=json.loads(data))
        assert response.status_code == 200
        response_data = response.json()
        assert (id_ := response_data.pop("id", None))
        bson.ObjectId(id_)  # check that the id is a valid object id
        assert {"user": data_requests[0]["user"], **json.loads(data)} == response_data

    async def test_invalid_authors(self, fake, async_client, collection_route):
        data = json.loads(fake.data_request().model_dump_json())
        data["authors"] = []
        response = await async_client.post(collection_route, json=data)
        assert response.status_code == 422

    async def test_invalid_uncollapsible_geometry(self, fake, async_client, collection_route):
        data = {
            **json.loads(fake.data_request().model_dump_json()),
            "geometry": json.loads(fake.uncollapsible_geojson().model_dump_json()),
        }
        response = await async_client.post(collection_route, json=data)
        assert response.status_code == 422


class TestPostUser(_TestPost, _TestUser): ...


class TestPostAdmin(_TestPost, _TestAdmin):
    @pytest.fixture
    def collection_route(self, data_requests):
        return f"/v1/admin/data-requests/?user={data_requests[0]['user']}"


class _TestUpdate:
    @pytest.fixture
    async def loaded_data(self, fake):
        model = json.loads(fake.data_request().model_dump_json())
        resp = await client.db.get_collection("data-request").insert_one(model)
        model.pop("_id")
        model["id"] = str(resp.inserted_id)
        return model

    @pytest.fixture
    async def data_requests(self, loaded_data):
        return [{"_id": loaded_data["id"], **loaded_data}]


class _TestPatch(_TestUpdate):
    async def test_valid(self, loaded_data, async_client, fake, member_route):
        title = fake.sentence()
        update = {"title": title}
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        assert loaded_data == response.json()

    async def test_valid_multiple(self, loaded_data, async_client, fake, member_route):
        title = fake.sentence()
        authors = [fake.author(), fake.author()]
        update = {"title": title, "authors": authors}
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        assert loaded_data == response.json()

    async def test_update_nothing(self, loaded_data, async_client, member_route):
        response = await async_client.patch(member_route, json={})
        assert response.status_code == 200
        assert loaded_data == response.json()

    async def test_no_id_update(self, loaded_data, async_client, member_route):
        update = {"id": str(bson.ObjectId())}
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        assert response.json()["id"] == loaded_data["id"]
        assert response.json()["id"] != update["id"]
        assert loaded_data == response.json()

    async def test_invalid_unset_value(self, async_client, member_route):
        response = await async_client.patch(member_route, json={"title": None})
        assert response.status_code == 422

    async def test_invalid_bad_type(self, async_client, member_route):
        response = await async_client.patch(member_route, json={"title": 10})
        assert response.status_code == 422

    async def test_invalid_uncollapsible_geometry(self, fake, async_client, member_route):
        response = await async_client.patch(
            member_route,
            json={"geometry": json.loads(fake.uncollapsible_geojson().model_dump_json())},
        )
        assert response.status_code == 422

    async def test_bad_id(self, async_client, collection_route):
        resp = await async_client.patch(f"{collection_route}/id-does-not-exist", json={})
        assert resp.status_code == 404, resp.json()


class TestPatchUser(_TestPatch, _TestUser):
    async def test_update_everything(self, loaded_data, async_client, fake, member_route):
        update = json.loads(fake.data_request().model_dump_json(exclude=["user"]))
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        update["id"] = loaded_data["id"]
        update["user"] = loaded_data["user"]
        assert update == response.json()

    async def test_no_update_user(self, loaded_data, async_client, member_route):
        new_user = loaded_data["user"] + "suffix"
        response = await async_client.patch(member_route, json={"user": new_user})
        assert response.status_code == 403


class TestPatchAdmin(_TestPatch, _TestAdmin):
    async def test_update_everything(self, loaded_data, async_client, fake, member_route):
        update = json.loads(fake.data_request().model_dump_json())
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        update["id"] = loaded_data["id"]
        assert update == response.json()

    async def test_update_user(self, loaded_data, async_client, member_route):
        new_user = loaded_data["user"] + "suffix"
        response = await async_client.patch(member_route, json={"user": new_user})
        assert response.status_code == 200
        assert response.json()["user"] == new_user


class _TestDelete(_TestUpdate):
    async def test_exists(self, loaded_data, async_client, member_route):
        response = await async_client.delete(member_route)
        assert response.status_code == 204
        resp = await client.db.get_collection("data-request").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is None

    async def test_bad_id(self, async_client, member_route):
        route = "/" + "/".join(member_route.strip("/").split("/")) + "bad-id-suffix"
        resp = await async_client.delete(route)
        assert resp.status_code == 404


class TestDeleteUser(_TestDelete, _TestUser):
    async def test_bad_user(self, loaded_data, async_client, member_route):
        route = f"/v1/users/someotheruser/data-requests/{loaded_data['id']}"
        response = await async_client.delete(route)
        assert response.status_code == 404


class TestDeleteAdmin(_TestDelete, _TestAdmin): ...
