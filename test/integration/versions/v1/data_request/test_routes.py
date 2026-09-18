import inspect
import json

import bson
import pytest
from stac_pydantic import Item

from marble_api.database import client
from marble_api.versions.v1.data_request.models import DataRequestPublic
from marble_api.versions.v1.data_request.routes import get_data_requests

from .....integration.utils._test_auth import AdminAuthTest, UserAuthTest
from .....integration.utils._test_routes import (
    GetManyTest,
    PreloadData,
    UpdateTest,
    assert_db_not_changed,
    compare_no_timestamps,
)

pytestmark = pytest.mark.anyio


class _TestUser(UserAuthTest):
    @pytest.fixture
    def user(self, records):
        return records[0]["user"]

    @pytest.fixture
    def member_route(self, records, user):
        return f"/v1/users/{user}/data-requests/{records[0].get('_id', 'should not get here')}"

    @pytest.fixture
    def collection_route(self, user):
        return f"/v1/users/{user}/data-requests/"


class _TestAdmin(AdminAuthTest):
    @pytest.fixture
    def member_route(self, records):
        return f"/v1/admin/data-requests/{records[0].get('_id', 'should not get here')}"

    @pytest.fixture
    def collection_route(self):
        return "/v1/admin/data-requests/"


class _TestGet(PreloadData):
    request_method = "get"
    collection_name = "data-request"

    @pytest.fixture(scope="class")
    @classmethod
    def fake_class(cls, fake):
        return fake.data_request


class _TestGetOne(_TestGet):
    request_path_type = "member"

    async def test_get(self, async_client, records, member_route):
        resp = await assert_db_not_changed(async_client.get(member_route), self.collection_name)
        assert resp.status_code == 200
        assert DataRequestPublic(**records[0]).model_dump() == DataRequestPublic(**resp.json()).model_dump()

    async def test_get_stac(self, async_client, member_route):
        resp = await assert_db_not_changed(async_client.get(f"{member_route}?stac=true"), self.collection_name)
        assert resp.status_code == 200
        assert (item := resp.json().get("stac_item"))
        Item(**item)

    async def test_bad_id(self, async_client, member_route):
        invalid_route = "/".join(member_route.split("/")[:-1] + ["some-bad-id"])
        resp = await assert_db_not_changed(async_client.get(invalid_route), self.collection_name)
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetOneUser(_TestGetOne, _TestUser):
    async def test_bad_user(self, async_client, records):
        invalid_route = f"/v1/users/{records[0]['user'] + '-bad-user'}/data-requests/{records[0]['_id']}"
        resp = await assert_db_not_changed(async_client.get(invalid_route), self.collection_name)
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetOneAdmin(_TestGetOne, _TestAdmin): ...


class _TestGetMany(_TestGet, GetManyTest):
    request_path_type = "collection"
    default_link_limit = inspect.signature(get_data_requests).parameters["limit"].default
    n_records = default_link_limit * 2 + 2
    n_records_return_count: int
    records_key = "data_requests"
    sort_keys = ("id", "user", "contact", "title", "created", "updated")

    async def test_get(self, async_client, records, collection_route):
        response = await assert_db_not_changed(async_client.get(collection_route), self.collection_name)

        models = {str(req["_id"]): DataRequestPublic(**req).model_dump() for req in records}
        for req in response.json()["data_requests"]:
            assert DataRequestPublic(**req).model_dump() == models[req["id"]]

    async def test_get_stac(self, async_client, collection_route):
        resp = await assert_db_not_changed(async_client.get(f"{collection_route}?stac=true"), self.collection_name)

        for req in resp.json()["data_requests"]:
            assert (item := req.get("stac_item"))
            Item(**item)


@pytest.mark.no_db_cleanup
class TestGetManyUser(_TestGetMany, _TestUser):
    n_records_return_count = _TestGetMany.n_records // 2

    async def test_get_all(self, async_client, collection_route):
        response = await assert_db_not_changed(
            async_client.get(f"{collection_route}?limit={self.n_records}"), self.collection_name
        )
        assert len(response.json()["data_requests"]) == self.n_records // 2


@pytest.mark.no_db_cleanup
class TestGetManyAdmin(_TestGetMany, _TestAdmin):
    n_records_return_count = _TestGetMany.n_records

    async def test_get_all(self, async_client, collection_route):
        response = await assert_db_not_changed(
            async_client.get(f"{collection_route}?limit={self.n_records}"), self.collection_name
        )

        assert len(response.json()["data_requests"]) == self.n_records


class _TestPost:
    request_method = "post"
    request_path_type = "collection"
    collection_name = "data-request"

    @pytest.fixture
    def records(self):
        return [{"user": "user1"}]

    async def test_valid(self, fake, async_client, collection_route, records):
        data = fake.data_request().model_dump_json(exclude=["user"])
        response = await async_client.post(collection_route, json=json.loads(data))
        assert response.status_code == 200
        response_data = response.json()
        assert (id_ := response_data.pop("id", None))
        bson.ObjectId(id_)  # check that the id is a valid object id
        compare_no_timestamps({"user": records[0]["user"], **json.loads(data)}, response_data)

    async def test_invalid_authors(self, fake, async_client, collection_route):
        data = json.loads(fake.data_request().model_dump_json())
        data["authors"] = []
        response = await assert_db_not_changed(async_client.post(collection_route, json=data), self.collection_name)
        assert response.status_code == 422

    async def test_invalid_uncollapsible_geometry(self, fake, async_client, collection_route):
        data = {
            **json.loads(fake.data_request().model_dump_json()),
            "geometry": json.loads(fake.uncollapsible_geojson().model_dump_json()),
        }
        response = await assert_db_not_changed(async_client.post(collection_route, json=data), self.collection_name)
        assert response.status_code == 422


class TestPostUser(_TestPost, _TestUser): ...


class TestPostAdmin(_TestPost, _TestAdmin):
    @pytest.fixture
    def collection_route(self, records):
        return f"/v1/admin/data-requests/?user={records[0]['user']}"


class _TestUpdate:
    request_path_type = "member"
    collection_name = "data-request"

    @pytest.fixture(autouse=True)
    async def loaded_data(self, fake):
        model = json.loads(fake.data_request().model_dump_json())
        resp = await client.db.get_collection("data-request").insert_one(model)
        model.pop("_id")
        model["id"] = str(resp.inserted_id)
        return model

    @pytest.fixture
    async def records(self, loaded_data):
        return [{"_id": loaded_data["id"], **loaded_data}]


class _TestPatch(_TestUpdate, UpdateTest):
    request_method = "patch"

    @pytest.fixture
    def valid_update(self):
        return {"title": "test123"}

    async def test_valid(self, loaded_data, async_client, fake, member_route):
        title = fake.sentence()
        update = {"title": title}
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        compare_no_timestamps(loaded_data, response.json())

    async def test_valid_multiple(self, loaded_data, async_client, fake, member_route):
        title = fake.sentence()
        authors = [fake.author(), fake.author()]
        update = {"title": title, "authors": authors}
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        loaded_data.update(update)
        compare_no_timestamps(loaded_data, response.json())

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


class TestPatchUser(_TestPatch, _TestUser):
    async def test_update_everything(self, loaded_data, async_client, fake, member_route):
        update = json.loads(fake.data_request().model_dump_json(exclude=["user"]))
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        update["id"] = loaded_data["id"]
        update["user"] = loaded_data["user"]
        compare_no_timestamps(update, response.json())

    async def test_no_update_user(self, loaded_data, async_client, member_route):
        new_user = loaded_data["user"] + "suffix"
        response = await assert_db_not_changed(
            async_client.patch(member_route, json={"user": new_user}), self.collection_name
        )
        assert response.status_code == 403


class TestPatchAdmin(_TestPatch, _TestAdmin):
    async def test_update_everything(self, loaded_data, async_client, fake, member_route):
        update = json.loads(fake.data_request().model_dump_json())
        response = await async_client.patch(member_route, json=update)
        assert response.status_code == 200
        update["id"] = loaded_data["id"]
        compare_no_timestamps(update, response.json())

    async def test_update_user(self, loaded_data, async_client, member_route):
        new_user = loaded_data["user"] + "suffix"
        response = await async_client.patch(member_route, json={"user": new_user})
        assert response.status_code == 200
        assert response.json()["user"] == new_user


class _TestDelete(_TestUpdate):
    request_method = "delete"

    async def test_exists(self, loaded_data, async_client, member_route):

        response = await async_client.delete(member_route)
        assert response.status_code == 204
        resp = await client.db.get_collection("data-request").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is None

    async def test_bad_id(self, async_client, member_route):
        route = "/" + "/".join(member_route.strip("/").split("/")) + "bad-id-suffix"
        resp = await assert_db_not_changed(async_client.delete(route), self.collection_name)
        assert resp.status_code == 404


class TestDeleteUser(_TestDelete, _TestUser):
    async def test_bad_user(self, loaded_data, async_client, member_route):
        route = f"/v1/users/someotheruser/data-requests/{loaded_data['id']}"
        response = await assert_db_not_changed(async_client.delete(route), self.collection_name)
        assert response.status_code == 404


class TestDeleteAdmin(_TestDelete, _TestAdmin): ...
