import datetime
from unittest.mock import AsyncMock, Mock, patch

import bson
import pytest
from fastapi import HTTPException, Response

from marble_api.utils.models import MarbleBaseModel, MarbleBaseModelUpdate, MarbleUserModel, MarbleUserModelPublic
from marble_api.utils.routes import delete_record, get_record, get_records, patch_record, post_record

pytestmark = pytest.mark.anyio


@pytest.fixture
def collection():
    coll = AsyncMock()

    # mock insert_one
    insert_one_return = Mock()
    insert_one_return.inserted_id = 123
    coll.insert_one.return_value = insert_one_return

    return_example = {"updated": datetime.datetime.now(tz=datetime.timezone.utc), "user": "test-user"}

    # mock find_one_and_update
    coll.find_one_and_update.return_value = {"_id": "find_one_and_update success", **return_example}

    # mock find_one
    coll.find_one.return_value = {"_id": "find_one success", **return_example}

    # mock delete_one
    delete_one_return = Mock()
    delete_one_return.deleted_count = 1
    coll.delete_one.return_value = delete_one_return

    return coll


def assert_approx_now(time, msg=""):
    assert datetime.datetime.now(tz=datetime.timezone.utc) - time < datetime.timedelta(seconds=1)


class TestPostRecord:
    async def test_no_user(self, collection):
        model = MarbleBaseModel()
        result = await post_record(collection, None, model)
        assert collection.insert_one.await_count == 1
        assert collection.insert_one.await_args.args[0] == result == {"id": "123", "updated": model.updated}

    async def test_sets_updated(self, collection):
        model = MarbleBaseModel()
        result = await post_record(collection, None, model)
        assert isinstance(model.updated, datetime.datetime)
        # check that the updated date is basically now
        assert_approx_now(model.updated)
        assert collection.insert_one.await_args.args[0]["updated"] == result["updated"] == model.updated

    async def test_with_user(self, collection):
        model = MarbleUserModel(user="test-user")
        result = await post_record(collection, "test-user", model)
        assert collection.insert_one.await_count == 1
        assert (
            collection.insert_one.await_args.args[0]
            == result
            == {"id": "123", "updated": model.updated, "user": "test-user"}
        )

    async def test_with_updated_user(self, collection):
        model = MarbleUserModel(user="test-user")
        result = await post_record(collection, "other-user", model)
        assert collection.insert_one.await_count == 1
        assert (
            collection.insert_one.await_args.args[0]
            == result
            == {"id": "123", "updated": model.updated, "user": "other-user"}
        )


class ModelUpdateExample(MarbleBaseModelUpdate):
    f: str


def _set_unset_ids(prefix):
    def _(val, _prefix=prefix):
        return _prefix + ("_set" if val else "_unset")

    return _


class TestPatchRecord:
    def assert_update_matches(self, update_arg, expected_update):
        assert list(update_arg.keys()) == ["$set"]
        assert set(update_arg["$set"]) == set(expected_update)
        for key in update_arg["$set"]:
            if key == "updated":
                assert_approx_now(update_arg["$set"][key])
            else:
                assert update_arg["$set"][key] == expected_update[key]

    @pytest.mark.parametrize("id_set", [True, False], ids=_set_unset_ids("id"))
    @pytest.mark.parametrize("user_set", [True, False], ids=_set_unset_ids("user"))
    @pytest.mark.parametrize("additional_selector_set", [True, False], ids=_set_unset_ids("additional_selector"))
    async def test_selectors(self, collection, id_set, user_set, additional_selector_set):
        id_ = bson.ObjectId() if id_set else None
        user = "test-user" if user_set else None
        additional_selector = {"other": "selector"} if additional_selector_set else None
        expected_selector = {
            k: v for k, v in {"_id": id_, "user": user, **(additional_selector or {})}.items() if v is not None
        }
        data = {"f": "test"}
        result = await patch_record(
            collection,
            id_=id_,
            user=user,
            additional_selector=additional_selector,
            data=data,
            validation_class=MarbleUserModelPublic,
        )
        assert result["_id"] == "find_one_and_update success"
        assert collection.find_one_and_update.await_count == 1
        await_args = collection.find_one_and_update.await_args.args
        assert await_args[0] == expected_selector
        self.assert_update_matches(await_args[1], {**data, "updated": None})  # None is a placeholder for now check

    @pytest.mark.parametrize("user_set", [True, False], ids=_set_unset_ids("user"))
    @pytest.mark.parametrize("allow_update_user", [True, False], ids=["allow_update", "disallow_update"])
    @pytest.mark.parametrize("user_update_set", [True, False], ids=_set_unset_ids("user_update"))
    async def test_allow_update_user(self, collection, user_set, allow_update_user, user_update_set):
        user = "test-user" if user_set else None
        data = {"user": "other-user"} if user_update_set else {}
        kwargs = dict(
            collection=collection,
            id_=None,
            user=user,
            data=data,
            allow_update_user=allow_update_user,
            validation_class=MarbleUserModelPublic,
        )
        if not allow_update_user and user_update_set:
            with pytest.raises(HTTPException) as e_info:
                await patch_record(**kwargs)
            assert e_info.value.status_code == 403
        else:
            await patch_record(**kwargs)

    @pytest.mark.parametrize("model_data", [True, False], ids=["model_data", "py_data"])
    async def test_update_model_data(self, collection, model_data):
        data = ModelUpdateExample(f="test") if model_data else {"f": "test"}
        result = await patch_record(collection, id_=None, user=None, data=data, validation_class=MarbleUserModelPublic)
        assert result["_id"] == "find_one_and_update success"
        assert collection.find_one_and_update.await_count == 1
        await_args = collection.find_one_and_update.await_args.args
        self.assert_update_matches(await_args[1], {"f": "test", "updated": None})  # None is a placeholder for now check

    async def test_no_update(self, collection):
        result = await patch_record(collection, id_=None, user=None, data={}, validation_class=MarbleUserModelPublic)
        assert result["_id"] == "find_one success"
        assert len(collection.find_one.await_args.args) == 1

    async def test_set_prefix(self, collection):
        result = await patch_record(
            collection,
            id_=None,
            user=None,
            data={"f": "test"},
            set_prefix="prefix.",
            validation_class=MarbleUserModelPublic,
        )
        assert result["_id"] == "find_one_and_update success"
        assert collection.find_one_and_update.await_count == 1
        await_args = collection.find_one_and_update.await_args.args
        self.assert_update_matches(
            await_args[1], {"prefix.f": "test", "updated": None}
        )  # None is a placeholder for now check

    @pytest.mark.parametrize("data_set", [True, False], ids=_set_unset_ids("data"))
    async def test_not_found(self, collection, data_set):
        data = {"f": "test"} if data_set else {}
        if data_set:
            collection.find_one_and_update.return_value = None
        else:
            collection.find_one.return_value = None
        with pytest.raises(HTTPException) as e_info:
            await patch_record(collection, id_=None, user=None, data=data, validation_class=MarbleUserModelPublic)
        assert e_info.value.status_code == 404


class TestGetRecord:
    @pytest.mark.parametrize("id_set", [True, False], ids=_set_unset_ids("id"))
    @pytest.mark.parametrize("user_set", [True, False], ids=_set_unset_ids("user"))
    @pytest.mark.parametrize("additional_selector_set", [True, False], ids=_set_unset_ids("additional_selector"))
    async def test_selectors(self, collection, id_set, user_set, additional_selector_set):
        id_ = bson.ObjectId() if id_set else None
        user = "test-user" if user_set else None
        additional_selector = {"other": "selector"} if additional_selector_set else None
        expected_selector = {
            k: v for k, v in {"_id": id_, "user": user, **(additional_selector or {})}.items() if v is not None
        }
        result = await get_record(collection, id_=id_, user=user, additional_selector=additional_selector)
        assert result["_id"] == "find_one success"
        assert collection.find_one.await_count == 1
        await_args = collection.find_one.await_args.args
        assert await_args[0] == expected_selector

    async def test_not_found(self, collection):
        collection.find_one.return_value = None
        with pytest.raises(HTTPException) as e_info:
            await get_record(collection, id_=None, user=None)
        assert e_info.value.status_code == 404


class TestGetRecords:
    @pytest.mark.parametrize("user_set", [True, False], ids=_set_unset_ids("user"))
    @pytest.mark.parametrize("additional_selector_set", [True, False], ids=_set_unset_ids("additional_selector"))
    @pytest.mark.parametrize("records_key_set", [True, False], ids=_set_unset_ids("records_key"))
    async def test_selectors(self, collection, user_set, additional_selector_set, records_key_set):
        user = "test-user" if user_set else None
        additional_selector = {"other": "selector"} if additional_selector_set else None
        other_kwargs = dict(
            collection=collection, request="test", limit=20, sort_by="f", after="after", before="before", ascending=True
        )
        expected_selector = {k: v for k, v in {"user": user, **(additional_selector or {})}.items() if v is not None}
        # NOTE: the behaviour of _paginated_query is tested in integration tests because it's behaviour is very closely
        #       tied to a valid Request object and database connection.
        with patch("marble_api.utils.routes._paginated_query", new_callable=AsyncMock) as mock:
            mock.return_value = "paginated_query success", "links"
            kwargs = {"user": user, "additional_selector": additional_selector, **other_kwargs}
            if records_key_set:
                kwargs["records_key"] = "new_key"
            result = await get_records(**kwargs)
            assert result == {
                ("new_key" if records_key_set else "records"): mock.return_value[0],
                "links": mock.return_value[1],
            }
            assert mock.await_count == 1
            assert mock.await_args.kwargs == {**other_kwargs, **expected_selector}


class TestDeleteRecord:
    @pytest.mark.parametrize("id_set", [True, False], ids=_set_unset_ids("id"))
    @pytest.mark.parametrize("user_set", [True, False], ids=_set_unset_ids("user"))
    @pytest.mark.parametrize("additional_selector_set", [True, False], ids=_set_unset_ids("additional_selector"))
    async def test_selectors(self, collection, id_set, user_set, additional_selector_set):
        id_ = bson.ObjectId() if id_set else None
        user = "test-user" if user_set else None
        additional_selector = {"other": "selector"} if additional_selector_set else None
        expected_selector = {
            k: v for k, v in {"_id": id_, "user": user, **(additional_selector or {})}.items() if v is not None
        }
        result = await delete_record(collection, id_=id_, user=user, additional_selector=additional_selector)
        assert isinstance(result, Response)
        assert result.status_code == 204

        assert collection.delete_one.await_count == 1
        await_args = collection.delete_one.await_args.args
        assert await_args[0] == expected_selector

    async def test_not_found(self, collection):
        delete_return_mock = Mock()
        delete_return_mock.deleted_count.return_value = 0
        collection.delete_one.return_value = delete_return_mock
        with pytest.raises(HTTPException) as e_info:
            await delete_record(collection, id_=None, user=None)
        assert e_info.value.status_code == 404
