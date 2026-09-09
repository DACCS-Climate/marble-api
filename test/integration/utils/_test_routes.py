import datetime
import json
from urllib.parse import parse_qs, urlparse

import bson
import pytest

from marble_api.database import client


def compare_no_timestamps(dict1, dict2, message=""):
    timestamps = {"created", "updated"}
    assert {k: v for k, v in dict1.items() if k not in timestamps} == {
        k: v for k, v in dict2.items() if k not in timestamps
    }, message


async def assert_db_not_changed(make_request, collection):
    before = await client.db.get_collection(collection).find({}).to_list()
    result = await make_request
    after = await client.db.get_collection(collection).find({}).to_list()
    assert before == after, "database has changed and it should not have"
    return result


class PreloadData:
    n_records = 2
    collection_name: str

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def load_data(cls, fake_class):
        if "user" in fake_class().model_dump():
            kwargs1 = {"user": "user1"}
            kwargs2 = {"user": "user2"}
        else:
            kwargs1 = kwargs2 = {}
        data = [json.loads(fake_class(**kwargs1).model_dump_json()) for _ in range(cls.n_records // 2)] + [
            json.loads(fake_class(**kwargs2).model_dump_json()) for _ in range(cls.n_records - cls.n_records // 2)
        ]
        await client.db.get_collection(cls.collection_name).insert_many(data)

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def cleanup(cls):
        try:
            yield
        finally:
            await client.drop_database(client.db.name)

    @pytest.fixture(scope="class")
    @classmethod
    async def records(cls):
        yield await client.db.get_collection(cls.collection_name).find({}).to_list()


class GetManyTest:
    default_link_limit: int
    n_records: int
    n_records_return_count: int
    records_key: str
    sort_keys: tuple[str]

    async def get_all_data(self, async_client, route):
        response = await async_client.get(route)
        data = []
        while True:
            data.extend(response.json()[self.records_key])
            for link in response.json()["links"]:
                if link["rel"] == "next":
                    response = await async_client.get(link["href"])
                    break
            else:
                break
        return data

    async def test_get_limit_default(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(collection_route), self.collection_name)
        assert len(response.json()[self.records_key]) == self.default_link_limit

    async def test_get_limit_non_default(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(f"{collection_route}?limit=5"), self.collection_name)
        assert len(response.json()[self.records_key]) == 5

    async def test_get_limit_more(self, async_client, collection_route):
        response = await assert_db_not_changed(
            async_client.get(f"{collection_route}?limit={self.n_records + 1}"), self.collection_name
        )
        assert len(response.json()[self.records_key]) == self.n_records_return_count

    async def test_get_limit_none(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(f"{collection_route}?limit=0"), self.collection_name)
        assert response.status_code == 422

    async def test_get_limit_over_max(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(f"{collection_route}?limit=200"), self.collection_name)
        assert response.status_code == 422

    @pytest.mark.parametrize("ascending", [True, False])
    async def test_sort_order_single_page(self, async_client, collection_route, ascending):
        for sort_by in self.sort_keys:
            response = await assert_db_not_changed(
                async_client.get(f"{collection_route}?sort_by={sort_by}&ascending={ascending}"), self.collection_name
            )
            data = [req[sort_by] for req in response.json()[self.records_key]]
            assert data == sorted(data, reverse=(not ascending))

    @pytest.mark.parametrize("ascending", [True, False])
    async def test_sort_order_multi_page(self, async_client, collection_route, ascending):
        for sort_by in self.sort_keys:
            data = await assert_db_not_changed(
                self.get_all_data(async_client, f"{collection_route}?sort_by={sort_by}&ascending={ascending}"),
                self.collection_name,
            )
            data = [(req[sort_by], req["id"]) for req in data]
            assert len(data) == self.n_records_return_count  # all data found
            assert len(data) == len(set(data))  # no duplicates
            assert data == sorted(data, reverse=(not ascending))  # in correct order

    async def test_get_first_page_links(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(collection_route), self.collection_name)
        links = response.json()["links"]
        assert len(links) == 1
        link = links[0]
        assert link["rel"] == "next"
        assert link["type"] == "application/json"
        assert link["href"].startswith(str(response.url))
        assert (after_id := parse_qs(urlparse(link["href"]).query).get("after"))
        assert after_id not in [r["id"] for r in response.json()[self.records_key]]

    async def test_get_last_page_links(self, async_client, collection_route):
        response = await assert_db_not_changed(
            async_client.get(f"{collection_route}?limit={self.n_records_return_count - 3}"), self.collection_name
        )
        next_link = next(link for link in response.json()["links"] if link["rel"] == "next")
        response2 = await async_client.get(next_link["href"])
        links = response2.json()["links"]
        assert len(links) == 1
        link = links[0]
        assert link["rel"] == "prev"
        assert link["type"] == "application/json"
        assert link["href"].startswith(str(response.url))
        assert (before_id := parse_qs(urlparse(link["href"]).query).get("before"))
        assert before_id not in [r["id"] for r in response.json()[self.records_key]]

    async def test_get_mid_page_links(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(f"{collection_route}?limit=4"), self.collection_name)
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
            assert id_ not in [r["id"] for r in response.json()[self.records_key]]

    async def test_next_prev_is_consistent(self, async_client, collection_route):
        response = await assert_db_not_changed(async_client.get(f"{collection_route}?limit=4"), self.collection_name)
        # page0 -> page1
        next_link = next(link for link in response.json()["links"] if link["rel"] == "next")
        next_response = await assert_db_not_changed(async_client.get(next_link["href"]), self.collection_name)
        # page0 -> page1 -> page2
        next_next_link = next(link for link in next_response.json()["links"] if link["rel"] == "next")
        next_next_response = await assert_db_not_changed(async_client.get(next_next_link["href"]), self.collection_name)
        # page0 -> page1 -> page0
        next_prev_link = next(link for link in next_response.json()["links"] if link["rel"] == "prev")
        next_prev_response = await assert_db_not_changed(async_client.get(next_prev_link["href"]), self.collection_name)
        # page0 -> page1 -> page2 -> page1
        next_next_prev_link = next(link for link in next_next_response.json()["links"] if link["rel"] == "prev")
        next_next_prev_response = await assert_db_not_changed(
            async_client.get(next_next_prev_link["href"]), self.collection_name
        )
        # page0 -> page1 -> page2 -> page1 -> page0
        next_next_prev_prev_link = next(
            link for link in next_next_prev_response.json()["links"] if link["rel"] == "prev"
        )
        next_next_prev_prev_response = await assert_db_not_changed(
            async_client.get(next_next_prev_prev_link["href"]), self.collection_name
        )
        assert response.json() == next_prev_response.json() == next_next_prev_prev_response.json()
        assert next_response.json() == next_next_prev_response.json()

    async def test_get_all_same_as_paging_next(self, async_client, collection_route):
        all_response = await assert_db_not_changed(
            async_client.get(f"{collection_route}?limit={self.n_records}"), self.collection_name
        )
        next_link = [f"{collection_route}?limit=4"]
        records = []
        while next_link:
            response = await assert_db_not_changed(async_client.get(next_link[0]), self.collection_name)
            records.extend(response.json()[self.records_key])
            next_link = [link["href"] for link in response.json()["links"] if link["rel"] == "next"]
        assert all_response.json()[self.records_key] == records


class UpdateTest:
    @pytest.fixture
    def client_method(self, async_client):
        return getattr(async_client, self.request_method.lower())

    async def test_no_id_update(self, loaded_data, client_method, member_route):
        update = {"id": str(bson.ObjectId())}
        response = await assert_db_not_changed(client_method(member_route, json=update), self.collection_name)
        assert response.status_code == 200
        assert response.json()["id"] == loaded_data["id"]
        assert response.json()["id"] != update["id"]
        compare_no_timestamps(loaded_data, response.json())

    async def test_update_nothing(self, loaded_data, client_method, member_route):
        response = await assert_db_not_changed(client_method(member_route, json={}), self.collection_name)
        assert response.status_code == 200
        compare_no_timestamps(loaded_data, response.json())

    async def test_bad_id(self, client_method, member_route, records):
        resp = await assert_db_not_changed(
            client_method(member_route.replace(records[0]["_id"], str(bson.ObjectId())), json={}), self.collection_name
        )
        assert resp.status_code == 404, resp.json()

    async def test_created_in_response(self, client_method, member_route, valid_update):
        response = await client_method(member_route, json=valid_update)
        assert response.status_code == 200, response.json()
        assert response.json()["created"]

    async def test_updated_updated(self, loaded_data, client_method, member_route, valid_update):
        response = await client_method(member_route, json=valid_update)
        assert response.status_code == 200, response.url
        assert loaded_data["updated"] != response.json()["updated"], response.json()

    @pytest.mark.parametrize("field", ["created", "updated"])
    async def test_no_updatable_timestamps(self, client_method, member_route, field, valid_update):
        new_date = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=10)
        valid_update[field] = new_date.isoformat()
        response = await client_method(member_route, json=valid_update)
        assert response.status_code == 200
        assert response.json()[field] != new_date.isoformat()
