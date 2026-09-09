import inspect
import json
from contextlib import asynccontextmanager

import bson
import pymongo
import pytest

from marble_api.database import client
from marble_api.versions.v1.survey.models import Survey, SurveyPublic
from marble_api.versions.v1.survey.routes import get_survey_responses, get_surveys

from .....integration.utils._test_auth import AdminAuthTest, UserAuthTest
from .....integration.utils._test_routes import (
    GetManyTest,
    PreloadData,
    UpdateTest,
    assert_db_not_changed,
    compare_no_timestamps,
)
from .....unit.utils.test_models import _create_model_func
from .....unit.utils.test_routes import assert_approx_now

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def _set_user_visible_false(record_id, collection):
    id_ = bson.ObjectId(record_id)
    resp = await client.db.get_collection(collection).find_one_and_update(
        {"_id": id_},
        {"$set": {"user_visible": False}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    assert not resp["user_visible"]
    yield
    resp = await client.db.get_collection(collection).find_one_and_update(
        {"_id": id_},
        {"$set": {"user_visible": True}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    assert resp["user_visible"]


class _TestGetSurvey(PreloadData):
    request_method = "get"
    collection_name = "survey"

    @pytest.fixture(scope="class")
    @classmethod
    def fake_class(cls, fake):
        return _create_model_func(fake.survey, user_visible=True)


class _TestGetOneSurvey(_TestGetSurvey):
    request_path_type = "member"

    @pytest.fixture
    async def set_user_visible_false(self, records):
        async with _set_user_visible_false(records[0]["_id"], self.collection_name):
            yield

    async def test_get(self, async_client, records, member_route):
        resp = await assert_db_not_changed(async_client.get(member_route), self.collection_name)
        assert resp.status_code == 200
        assert SurveyPublic(**records[0]).model_dump() == SurveyPublic(**resp.json()).model_dump()

    async def test_bad_id(self, async_client, member_route):
        invalid_route = "/".join(member_route.split("/")[:-1] + ["some-bad-id"])
        resp = await assert_db_not_changed(async_client.get(invalid_route), self.collection_name)
        assert resp.status_code == 404


class _TestGetManySurvey(_TestGetSurvey, GetManyTest):
    request_path_type = "collection"
    default_link_limit = inspect.signature(get_surveys).parameters["limit"].default
    n_records = default_link_limit * 2 + 2
    n_records_return_count: int
    records_key = "surveys"
    sort_keys = ("id", "created", "updated", "user_visible")

    @pytest.fixture(autouse=True, scope="class")
    @classmethod
    async def set_half_user_visible_false(cls, load_data, records):
        for record in records[: len(records) // 2]:
            id_ = bson.ObjectId(record["_id"])
            assert await client.db.get_collection(cls.collection_name).find({}).to_list()
            resp = await client.db.get_collection(cls.collection_name).find_one_and_update(
                {"_id": id_},
                {"$set": {"user_visible": False}},
                return_document=pymongo.ReturnDocument.AFTER,
            )
            assert not resp["user_visible"]
        yield


class _TestPostSurvey:
    request_method = "post"
    request_path_type = "collection"
    collection_name = "survey"


class _TestUpdateSurvey:
    request_path_type = "member"
    collection_name = "survey"

    @pytest.fixture(autouse=True)
    async def loaded_data(self, fake):
        model = json.loads(fake.survey(user_visible=False).model_dump_json())
        resp = await client.db.get_collection("survey").insert_one(model)
        model.pop("_id")
        model["id"] = str(resp.inserted_id)
        return model

    @pytest.fixture
    async def records(self, loaded_data):
        return [{"_id": loaded_data["id"], **loaded_data}]

    async def check_loaded_data_unchanged_in_db(self, loaded_data):
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert Survey(**resp).model_dump() == Survey(**loaded_data).model_dump()


class _TestPatchSurvey(_TestUpdateSurvey, UpdateTest):
    request_method = "patch"

    @pytest.fixture
    def valid_update(self):
        return {"user_visible": False}

    async def test_update_user_visible(self, async_client, member_route, loaded_data):
        resp = await async_client.patch(member_route, json={"user_visible": True})
        assert resp.status_code == 200
        assert resp.json()["user_visible"]
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp["user_visible"]

    async def test_update_questions_exist(self, fake, async_client, member_route, loaded_data):
        questions = [json.loads(q.model_dump_json()) for q in fake.survey().questions]
        resp = await async_client.patch(member_route, json={"questions": questions})
        assert resp.status_code == 200
        assert resp.json()["questions"] == questions
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        for question in resp["questions"]:
            if question["pattern"]:
                question["pattern"] = question["pattern"].pattern
        assert resp["questions"] == questions

    async def test_no_update_questions_if_user_visible(self, async_client, member_route, fake, loaded_data):
        resp = await async_client.patch(member_route, json={"user_visible": True})
        assert resp.status_code == 200
        resp2 = await async_client.patch(
            member_route, json={"questions": [json.loads(q.model_dump_json()) for q in fake.survey().questions]}
        )
        assert resp2.status_code == 403
        await self.check_loaded_data_unchanged_in_db(resp.json())

    async def test_update_user_visible_if_user_visible(self, async_client, member_route, loaded_data):
        resp = await async_client.patch(member_route, json={"user_visible": True})
        assert resp.status_code == 200
        resp = await async_client.patch(member_route, json={"user_visible": False})
        assert resp.status_code == 200
        assert not resp.json()["user_visible"]
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert not resp["user_visible"]

    async def test_no_update_questions_if_responses_exist(self, fake, loaded_data, async_client, member_route):
        model = json.loads(fake.response(for_survey=Survey(**loaded_data)).model_dump_json())
        resp = await client.db.get_collection("survey-response").insert_one(model)
        resp = await assert_db_not_changed(
            async_client.patch(
                member_route, json={"questions": [json.loads(q.model_dump_json()) for q in fake.survey().questions]}
            ),
            self.collection_name,
        )
        assert resp.status_code == 403
        # check that the value in the database was not updated
        await self.check_loaded_data_unchanged_in_db(loaded_data)

    async def test_update_user_visible_if_responses_exist(self, fake, loaded_data, async_client, member_route):
        model = json.loads(fake.response(for_survey=Survey(**loaded_data)).model_dump_json())
        resp = await client.db.get_collection("survey-response").insert_one(model)
        resp = await async_client.patch(member_route, json={"user_visible": True})
        assert resp.status_code == 200
        assert resp.json()["user_visible"]
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp["user_visible"]

    async def test_patch_invalid_update(self, fake, loaded_data, async_client, member_route):
        invalid_question = json.loads(fake.text_question().model_dump_json())
        invalid_question["min_length"] = 7
        invalid_question["max_length"] = 5
        resp = await assert_db_not_changed(
            async_client.patch(member_route, json={"questions": [invalid_question]}), self.collection_name
        )
        assert resp.status_code == 422
        # check that the value in the database was not updated (rolled back!)
        await self.check_loaded_data_unchanged_in_db(loaded_data)


class _TestDeleteSurvey(_TestUpdateSurvey):
    request_method = "delete"

    async def test_no_delete_if_user_visible(self, async_client, member_route, loaded_data):
        resp = await async_client.patch(member_route, json={"user_visible": True})
        assert resp.status_code == 200
        resp = await assert_db_not_changed(
            async_client.delete(
                member_route,
            ),
            self.collection_name,
        )
        assert resp.status_code == 403
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is not None

    async def test_no_delete_if_responses_exist(self, fake, loaded_data, async_client, member_route):
        model = json.loads(fake.response(for_survey=Survey(**loaded_data)).model_dump_json())
        resp = await client.db.get_collection("survey-response").insert_one(model)
        resp = await assert_db_not_changed(async_client.delete(member_route), self.collection_name)
        assert resp.status_code == 403
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is not None

    async def test_delete_success(self, loaded_data, async_client, member_route):
        resp = await async_client.delete(member_route)
        assert resp.status_code == 204
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        assert resp is None


class _TestSurveyUser(UserAuthTest):
    @pytest.fixture
    def user(self):
        return "test-user"

    @pytest.fixture
    def records(self):
        return [{"_id": "something"}]

    @pytest.fixture
    def member_route(self, records, user):
        return f"/v1/users/{user}/surveys/{records[0].get('_id', 'should not get here')}"

    @pytest.fixture
    def collection_route(self, user):
        return f"/v1/users/{user}/surveys/"


class _TestSurveyAdmin(AdminAuthTest):
    @pytest.fixture
    def member_route(self, records):
        return f"/v1/admin/surveys/{records[0].get('_id', 'should not get here')}"

    @pytest.fixture
    def collection_route(self):
        return "/v1/admin/surveys/"


class TestPostSurveyAdmin(_TestPostSurvey, _TestSurveyAdmin):
    @pytest.fixture
    def records(self):
        return [{"user": "user1", "_id": "something"}]

    async def test_valid(self, fake, async_client, collection_route):
        data = fake.survey().model_dump_json()
        response = await async_client.post(collection_route, json=json.loads(data))
        assert response.status_code == 200
        response_data = response.json()
        assert (id_ := response_data.pop("id", None))
        bson.ObjectId(id_)  # check that the id is a valid object id
        compare_no_timestamps(json.loads(data), response_data)

    async def test_invalid(self, fake, async_client, collection_route):
        data = json.loads(fake.survey().model_dump_json())
        data["questions"][0]["text"] = None
        response = await assert_db_not_changed(async_client.post(collection_route, json=data), self.collection_name)
        assert response.status_code == 422


class TestPatchSurveyAdmin(_TestPatchSurvey, _TestSurveyAdmin): ...


class TestDeleteSurveyAdmin(_TestDeleteSurvey, _TestSurveyAdmin): ...


@pytest.mark.no_db_cleanup
class TestGetSurveyUser(_TestGetOneSurvey, _TestSurveyUser):
    async def test_get_no_user_visible(self, async_client, set_user_visible_false, member_route):
        resp = await assert_db_not_changed(async_client.get(member_route), self.collection_name)
        assert resp.status_code == 404


@pytest.mark.no_db_cleanup
class TestGetSurveyAdmin(_TestGetOneSurvey, _TestSurveyAdmin):
    async def test_get_no_user_visible(self, async_client, records, set_user_visible_false, member_route):
        resp = await assert_db_not_changed(async_client.get(member_route), self.collection_name)
        assert resp.status_code == 200
        expected_record = {**records[0], "user_visible": False}
        assert SurveyPublic(**expected_record).model_dump() == SurveyPublic(**resp.json()).model_dump()


@pytest.mark.no_db_cleanup
class TestGetSurveysUser(_TestGetManySurvey, _TestSurveyUser):
    n_records_return_count = _TestGetManySurvey.n_records // 2

    async def test_get_user_visible_only(self, async_client, collection_route):
        data = await assert_db_not_changed(self.get_all_data(async_client, collection_route), self.collection_name)
        assert all(survey["user_visible"] for survey in data)


@pytest.mark.no_db_cleanup
class TestGetSurveysAdmin(_TestGetManySurvey, _TestSurveyAdmin):
    n_records_return_count = _TestGetManySurvey.n_records

    async def test_visible_and_hidden(self, async_client, collection_route):
        data = await assert_db_not_changed(self.get_all_data(async_client, collection_route), self.collection_name)
        assert set(survey["user_visible"] for survey in data) == {True, False}


class TestPatchSurveyQuestionAdmin(_TestUpdateSurvey, _TestSurveyAdmin):
    request_method = "patch"

    @pytest.fixture
    def member_route(self, records):
        return f"/v1/admin/surveys/{records[0].get('_id', 'should not get here')}/questions/0"

    async def test_no_patch_if_user_visible(self, async_client, member_route, loaded_data, fake):
        resp = await async_client.patch(f"/v1/admin/surveys/{loaded_data['id']}", json={"user_visible": True})
        assert resp.status_code == 200
        resp2 = await assert_db_not_changed(
            async_client.patch(member_route, json=json.loads(fake.question().model_dump_json())), self.collection_name
        )
        assert resp2.status_code == 403
        await self.check_loaded_data_unchanged_in_db(resp.json())

    async def test_no_patch_if_responses_exist(self, fake, loaded_data, async_client, member_route):
        model = json.loads(fake.response(for_survey=Survey(**loaded_data)).model_dump_json())
        resp = await client.db.get_collection("survey-response").insert_one(model)
        resp = await assert_db_not_changed(
            async_client.patch(member_route, json=json.loads(fake.question().model_dump_json())), self.collection_name
        )
        assert resp.status_code == 403
        await self.check_loaded_data_unchanged_in_db(loaded_data)

    async def test_patch_index_out_of_bounds(self, fake, loaded_data, async_client, member_route):
        member_route = member_route[:-1] + str(len(loaded_data["questions"]))
        question = json.loads(fake.question().model_dump_json())
        resp = await async_client.patch(member_route, json=question)
        assert resp.status_code == 200
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        expected_survey = Survey(**{**loaded_data, "questions": loaded_data["questions"] + [question]})
        assert resp["updated"] > expected_survey.updated
        assert Survey(**resp).model_dump(exclude=["updated"]) == expected_survey.model_dump(exclude=["updated"])

    async def test_patch_success(self, loaded_data, async_client, member_route, fake):
        question = json.loads(fake.question().model_dump_json())
        resp = await async_client.patch(member_route, json=question)
        assert resp.status_code == 200
        resp = await client.db.get_collection("survey").find_one({"_id": bson.ObjectId(loaded_data["id"])})
        expected_survey = Survey(**{**loaded_data, "questions": [question] + loaded_data["questions"][1:]})
        assert resp["updated"] > expected_survey.updated
        assert Survey(**resp).model_dump(exclude=["updated"]) == expected_survey.model_dump(exclude=["updated"])


class _TestSurveyResponseUser(UserAuthTest):
    @pytest.fixture
    def user(self, records):
        return records[0]["user"]

    @pytest.fixture
    def records(self):
        return [{"user": "user1", "survey_id": "something"}]

    @pytest.fixture
    def member_route(self, records, user):
        return f"/v1/users/{user}/surveys/{records[0]['survey_id']}/response"

    @pytest.fixture
    def collection_route(self, member_route):
        return member_route  # only one response per user per survey allowed so there is no distinction

    async def test_survey_not_visible(self, records, make_request):
        async with _set_user_visible_false(records[0]["survey_id"], "survey"):
            resp = await assert_db_not_changed(make_request, self.collection_name)
        assert resp.status_code == 404


class _TestSurveyResponseAdmin(AdminAuthTest):
    @pytest.fixture
    def member_route(self, records):
        return f"/v1/admin/survey-responses/{records[0]['_id']}"

    @pytest.fixture
    def collection_route(self):
        return "/v1/admin/survey-responses/"


class _TestGetSurveyResponse(PreloadData):
    request_method = "get"
    collection_name = "survey-response"

    @pytest.fixture(scope="class")
    @classmethod
    def fake_class(cls, fake):
        return fake.response

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    async def load_data(cls, fake):
        surveys = [fake.survey(user_visible=True) for _ in range(cls.n_records)]
        survey_ids = await client.db.get_collection("survey").insert_many(
            [json.loads(survey.model_dump_json()) for survey in surveys]
        )
        for i, id_ in enumerate(survey_ids.inserted_ids):
            surveys[i].id = id_
        responses = [fake.response(user="user1", for_survey=surveys[i]) for i in range(cls.n_records // 2)] + [
            fake.response(user="user2", for_survey=surveys[i]) for i in range(cls.n_records // 2, cls.n_records)
        ]
        await client.db.get_collection(cls.collection_name).insert_many(
            [json.loads(resp.model_dump_json()) for resp in responses]
        )


class _TestGetOneSurveyResponse(_TestGetSurveyResponse):
    request_path_type = "member"


class _TestGetManySurveyResponse(_TestGetSurveyResponse, GetManyTest):
    request_path_type = "collection"
    default_link_limit = inspect.signature(get_survey_responses).parameters["limit"].default
    n_records = default_link_limit * 2 + 2
    n_records_return_count = n_records
    records_key = "survey_responses"
    sort_keys = ("id", "created", "updated", "survey_id")


class _TestUpdatePostSurveyResponse:
    collection_name = "survey-response"

    @pytest.fixture(autouse=True)
    async def loaded_survey(self, fake, faker_providers):
        choices = {"a": "a", "b": "b", "c": "c", "d": "d", "e": "e"}
        survey = fake.survey(
            user_visible=True,
            questions=[
                fake.text_question(required=False, min_length=1, max_length=10, pattern=None),
                fake.text_question(
                    required=True,
                    min_length=1,
                    max_length=10,
                    pattern=faker_providers["SurveyProvider"].example_pattern,
                ),
                fake.choice_question(required=False, min_choices=2, max_choices=4, choices=choices, allow_others=False),
                fake.choice_question(
                    required=True,
                    min_choices=2,
                    max_choices=4,
                    allow_others=True,
                    choices=choices,
                    min_length=1,
                    max_length=10,
                    pattern=faker_providers["SurveyProvider"].example_pattern,
                ),
            ],
        )
        resp = await client.db.get_collection("survey").insert_one(json.loads(survey.model_dump_json()))
        survey.id = resp.inserted_id
        return survey


class _TestUpdateSurveyResponse(_TestUpdatePostSurveyResponse):
    @pytest.fixture(autouse=True)
    async def loaded_data(self, fake, loaded_survey):
        response_data = json.loads(fake.response(user="user1", for_survey=loaded_survey).model_dump_json())
        resp = await client.db.get_collection("survey-response").insert_one(response_data)
        response_data.pop("_id")
        response_data["id"] = str(resp.inserted_id)
        return response_data

    @pytest.fixture
    async def records(self, loaded_data):
        return [{"_id": loaded_data["id"], **loaded_data}]


class _TestPutSurveyResponse(_TestUpdateSurveyResponse, UpdateTest):
    request_method = "put"
    request_path_type = "member"

    @pytest.fixture
    def valid_update(self, fake, loaded_survey):
        valid = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        return {"answers": valid["answers"]}

    async def test_bad_id(self, client_method, collection_route, records):
        route = collection_route.replace(records[0]["survey_id"], "id-does-not-exist")
        resp = await assert_db_not_changed(client_method(route, json={}), self.collection_name)
        assert resp.status_code == 404, resp.url


class _TestPostSurveyResponse(_TestUpdatePostSurveyResponse):
    request_method = "post"
    request_path_type = "collection"

    @pytest.fixture
    async def records(self, loaded_survey):
        return [{"_id": bson.ObjectId(), "user": "user1", "survey_id": loaded_survey.id}]


class _TestDeleteSurveyResponse(_TestUpdateSurveyResponse):
    request_method = "delete"
    request_path_type = "member"


class TestPostSurveyResponseUser(_TestPostSurveyResponse, _TestSurveyResponseUser):
    async def test_response_not_valid(self, loaded_survey, fake, async_client, member_route):
        response = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        response["answers"] = []
        resp = await assert_db_not_changed(async_client.post(member_route, json=response), self.collection_name)
        assert resp.status_code == 422

    async def test_response_valid(self, loaded_survey, fake, async_client, member_route, user):
        data = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        resp = await async_client.post(member_route, json=data)
        assert resp.status_code == 200
        response_data = resp.json()
        assert (id_ := response_data.pop("id", None))
        data["user"] = user  # check that the user from the path is set
        id_ = bson.ObjectId(id_)  # check that the id is a valid object id
        compare_no_timestamps(data, response_data)
        db_value = await client.db.get_collection("survey-response").find_one({"_id": id_})
        assert db_value["answers"] == response_data["answers"]
        assert_approx_now(db_value["updated"])

    async def test_multiple_valid_responses(self, loaded_survey, fake, async_client, member_route):
        data = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        resp = await async_client.post(member_route, json=data)
        assert resp.status_code == 200
        data2 = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        resp = await assert_db_not_changed(async_client.post(member_route, json=data2), self.collection_name)
        assert resp.status_code == 409


class TestPutSurveyResponseUser(_TestPutSurveyResponse, _TestSurveyResponseUser):
    async def test_response_not_valid(self, loaded_survey, fake, async_client, member_route, records):
        response = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        response["answers"] = []
        resp = await assert_db_not_changed(async_client.put(member_route, json=response), self.collection_name)
        assert resp.status_code == 422

    async def test_response_update_survey_id(self, loaded_survey, fake, async_client, member_route, records):
        resp = await client.db.get_collection("survey").insert_one(json.loads(loaded_survey.model_dump_json()))
        new_id = resp.inserted_id
        response = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        response["survey_id"] = str(new_id)
        resp = await assert_db_not_changed(async_client.put(member_route, json=response), self.collection_name)
        assert resp.status_code == 403

    async def test_response_valid(self, loaded_survey, fake, async_client, member_route):
        data = json.loads(fake.response(for_survey=loaded_survey).model_dump_json())
        resp = await async_client.put(member_route, json={"answers": data["answers"]})
        assert resp.status_code == 200
        response_data = resp.json()
        assert (id_ := response_data.pop("id", None))
        id_ = bson.ObjectId(id_)  # check that the id is a valid object id
        db_value = await client.db.get_collection("survey-response").find_one({"_id": id_})
        assert db_value["answers"] == response_data["answers"] == data["answers"]
        assert_approx_now(db_value["updated"])


class TestPatchSurveyResponseUser(_TestUpdateSurveyResponse, _TestSurveyResponseUser):
    request_method = "patch"
    request_path_type = "member"

    @pytest.fixture
    def member_route(self, records):
        return f"/v1/users/{records[0]['user']}/surveys/{records[0]['survey_id']}/response/0"

    async def test_answer_not_valid(self, loaded_survey, async_client, member_route, records):
        data = "a" * (loaded_survey.questions[0].max_length + 1)
        resp = await assert_db_not_changed(async_client.patch(member_route, json=data), self.collection_name)
        assert resp.status_code == 422

    async def test_answer_index_out_of_bounds(self, loaded_survey, async_client, member_route, records):
        resp = await assert_db_not_changed(
            async_client.patch(member_route[:-1] + str(len(loaded_survey.questions)), json="a"), self.collection_name
        )
        assert resp.status_code == 404

    async def test_answer_valid(self, async_client, member_route, records):
        if records[0]["answers"][0] is None:
            answer = "aa"
            resp = await async_client.patch(member_route, json=answer)
        else:
            answer = None
            resp = await async_client.patch(member_route)
        assert resp.status_code == 200, resp.json()
        resp = await client.db.get_collection("survey-response").find_one({"_id": bson.ObjectId(records[0]["id"])})
        assert resp["answers"][0] == answer


@pytest.mark.no_db_cleanup
class TestGetSurveyResponseUser(_TestGetOneSurveyResponse, _TestSurveyResponseUser):
    async def test_survey_visible(self, make_request):
        resp = await make_request
        assert resp.status_code == 200
        response_data = resp.json()
        assert (id_ := response_data.get("id"))
        id_ = bson.ObjectId(id_)  # check that the id is a valid object id
        db_value = await client.db.get_collection("survey-response").find_one({"_id": id_})
        db_value["id"] = str(db_value.pop("_id"))
        compare_no_timestamps(db_value, response_data)


@pytest.mark.no_db_cleanup
class TestGetSurveyResponseAdmin(_TestGetOneSurveyResponse, _TestSurveyResponseAdmin):
    @pytest.mark.parametrize("visible", [True, False], ids=["visible", "not_visible"])
    async def test_survey_visible(self, make_request, visible, records):
        if visible:
            resp = await make_request
        else:
            async with _set_user_visible_false(records[0]["survey_id"], "survey"):
                resp = await make_request
        assert resp.status_code == 200
        response_data = resp.json()
        assert (id_ := response_data.get("id"))
        id_ = bson.ObjectId(id_)  # check that the id is a valid object id
        db_value = await client.db.get_collection("survey-response").find_one({"_id": id_})
        db_value["id"] = str(db_value.pop("_id"))
        compare_no_timestamps(db_value, response_data)


class TestDeleteSurveyResponseAdmin(_TestDeleteSurveyResponse, _TestSurveyResponseAdmin):
    @pytest.mark.parametrize("visible", [True, False], ids=["visible", "not_visible"])
    async def test_survey_visible(self, make_request, visible, records):
        if visible:
            resp = await make_request
        else:
            async with _set_user_visible_false(records[0]["survey_id"], "survey"):
                resp = await make_request
        assert resp.status_code == 204
        db_value = await client.db.get_collection("survey-response").find_one({})
        assert db_value is None


@pytest.mark.no_db_cleanup
class TestGetSurveyResponsesAdmin(_TestGetManySurveyResponse, _TestSurveyResponseAdmin): ...


@pytest.mark.no_db_cleanup
class TestInvalidRoutes(_TestGetSurveyResponse):
    # subclass _TestGetSurveyResponse so that valid data is loaded to the db
    @pytest.mark.parametrize(
        "method_route",
        (
            ("post", "/v1/users/user1/surveys/", 405),
            ("patch", f"/v1/users/user1/surveys/{bson.ObjectId()}", 405),
            ("patch", f"/v1/users/user1/surveys/{bson.ObjectId()}/questions/0", 404),
            ("delete", f"/v1/users/user1/surveys/{bson.ObjectId()}", 405),
            ("post", f"/v1/admin/surveys/{bson.ObjectId()}/response", 404),
            ("put", f"/v1/admin/surveys/{bson.ObjectId()}/response", 404),
            ("patch", f"/v1/admin/surveys/{bson.ObjectId()}/response/0", 404),
            ("get", f"/v1/admin/surveys/{bson.ObjectId()}/response", 404),
            ("get", f"/v1/users/user1/survey-responses/{bson.ObjectId()}", 404),
            ("delete", f"/v1/users/user1/survey-responses/{bson.ObjectId()}", 404),
            ("get", "/v1/users/user1/survey-responses/", 404),
        ),
        ids=lambda val: ", ".join([str(v) for v in val]),
    )
    async def test_routes_that_are_not_allowed_or_do_not_exist(self, async_client, method_route):
        method, route, status = method_route
        resp = await assert_db_not_changed(
            assert_db_not_changed(getattr(async_client, method)(route), "survey"), "survey-response"
        )
        assert resp.status_code == status
