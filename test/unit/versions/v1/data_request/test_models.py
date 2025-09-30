import datetime

import pytest
from pydantic import TypeAdapter, ValidationError
from pystac import Item

from marble_api.versions.v1.data_request.models import Author, DataRequestUpdate


class TestAuthor:
    validator = TypeAdapter(Author)

    def test_all(self):
        author = Author(first_name="first", last_name="last", email="email@example.com")
        self.validator.validate_python(author)

    def test_minimal(self):
        author = Author(last_name="last")
        self.validator.validate_python(author)

    def test_invalid_email(self):
        author = Author(last_name="last", email="not an email")
        with pytest.raises(ValidationError):
            self.validator.validate_python(author)


class TestDataRequest:
    @pytest.fixture
    def fake_class(self, fake):
        return fake.data_request

    def test_id_dumped(self, fake_class):
        assert "id" not in fake_class().model_dump()

    @pytest.mark.parametrize("field", ["user", "title", "description", "authors", "path", "contact"])
    def test_text_fields_not_empty(self, fake_class, field):
        with pytest.raises(ValidationError):
            fake_class(**{field: ""})

    @pytest.mark.parametrize(
        "field",
        [
            "user",
            "title",
            "authors",
            "temporal",
            "links",
            "path",
            "contact",
            "additional_paths",
            "variables",
            "extra_properties",
        ],
    )
    def test_fields_not_nullable(self, fake_class, field):
        with pytest.raises(ValidationError):
            fake_class(**{field: None})

    @pytest.mark.parametrize(
        "field",
        [
            "description",
            "additional_paths",
            "variables",
            "extra_properties",
        ],
    )
    def test_fields_default_if_unset(self, fake_class, field):
        request = fake_class(unset=[field])
        assert request.model_dump()[field] == type(request).model_fields[field].default

    def test_id_is_str(self, fake_class):
        assert isinstance(fake_class().id, str)

    def test_temporal_sorted(self, fake_class):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        temporal = [now, now - datetime.timedelta(hours=1)]
        request = fake_class(temporal=temporal)
        assert request.temporal == temporal[::-1]

    def test_temporal_tzaware(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(temporal=[datetime.datetime.now()])


class TestDataRequestPublic(TestDataRequest):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.data_request_public

    def test_id_dumped(self, fake_class):
        assert "id" in fake_class().model_dump()

    class TestStacItem:
        def test_valid(self, fake_class):
            assert Item.from_dict(fake_class().stac_item)

        def test_geometry(self, fake_class):
            request = fake_class()
            assert request.stac_item["geometry"] == request.geometry.model_dump()
            assert request.stac_item["bbox"]

        def test_null_geometry(self, fake_class):
            request = fake_class(geometry=None)
            assert request.stac_item["geometry"] is None
            assert request.stac_item["bbox"] is None

        def test_single_temporal(self, fake_class):
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            request = fake_class(temporal=[now])
            assert request.stac_item["properties"]["datetime"] == now.isoformat()
            assert "start_datetime" not in request.stac_item["properties"]
            assert "end_datetime" not in request.stac_item["properties"]

        def test_range_temporal(self, fake_class):
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            temporal = [now, now + datetime.timedelta(hours=1)]
            request = fake_class(temporal=temporal)
            assert request.stac_item["properties"]["datetime"] == temporal[0].isoformat()
            assert request.stac_item["properties"]["start_datetime"] == temporal[0].isoformat()
            assert request.stac_item["properties"]["end_datetime"] == temporal[1].isoformat()

        def test_extra_properties(self, fake_class):
            request = fake_class()
            item = request.stac_item
            assert set(request.extra_properties) & set(item["properties"]) == set(request.extra_properties)

        def test_links(self, fake_class):
            request = fake_class()
            assert request.links.model_dump() == request.stac_item["links"]

        def test_id(self, fake_class):
            request = fake_class()
            assert request.id == request.stac_item["id"]


class TestDataRequestUpdate(TestDataRequest):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.data_request_update

    def test_all_fields_optional(self):
        DataRequestUpdate()

    def test_all_defaults_none(self):
        assert all(field.default is None for field in DataRequestUpdate.model_fields.values())
