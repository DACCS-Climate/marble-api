import datetime

import bson
import pytest
from faker import Faker
from faker.providers import BaseProvider

from marble_api.versions.v1.data_request.models import DataRequest, DataRequestPublic, DataRequestUpdate


class GeoJsonProvider(BaseProvider):
    def point(self, dimensions=None):
        point = [self.generator.random.uniform(-180, 180), self.generator.random.uniform(-90, 90)]
        if dimensions == 3 or (dimensions is None and self.generator.pybool()):
            point.append(self.generator.random.uniform(-100, 100))
        return point

    def bbox(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.pybool()
        return [a for b in zip(*(sorted(x) for x in zip(self.point(dimensions), self.point(dimensions)))) for a in b]

    def line(self, dimensions=None):
        return [self.point(dimensions) for _ in range(self.generator.pyint(min_value=2, max_value=12))]

    def linear_ring(self, dimensions=None):
        ring = [self.point(dimensions) for _ in range(self.generator.random.randint(3, 100))]
        ring.append(list(ring[0]))
        return ring

    def _geo_base(self):
        base = {}
        if self.generator.random.random() < 0.5:
            base["bbox"] = self.bbox()
        return base

    def geo_point(self, dimensions=None):
        return {**self._geo_base(), "type": "Point", "coordinates": self.point(dimensions)}

    def geo_multipoint(self, dimensions=None):
        return {
            **self._geo_base(),
            "type": "MultiPoint",
            "coordinates": [self.point(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
        }

    def geo_linestring(self, dimensions=None):
        return {**self._geo_base(), "type": "LineString", "coordinates": self.line(dimensions)}

    def geo_multilinestring(self, dimensions=None):
        return {
            **self._geo_base(),
            "type": "MultiLineString",
            "coordinates": [self.line(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
        }

    def geo_polygon(self, dimensions=None):
        return {**self._geo_base(), "type": "Polygon", "coordinates": [self.linear_ring(dimensions)]}

    def geo_multipolygon(self, dimensions=None):
        return {
            **self._geo_base(),
            "type": "MultiPolygon",
            "coordinates": [
                [self.linear_ring(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))]
            ],
        }

    def geometry(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.random.choice([3, 2, None])
        return self.generator.random.choice(
            [
                self.geo_point,
                self.geo_multipoint,
                self.geo_linestring,
                self.geo_multilinestring,
                self.geo_polygon,
                self.geo_multipolygon,
            ]
        )(dimensions)


class DataRequestProvider(GeoJsonProvider):
    def author(self):
        author_ = {"last_name": self.generator.last_name()}
        if self.generator.pybool():
            author_["first_name"] = self.generator.first_name()
        if self.generator.pybool():
            author_["email"] = self.generator.email()
        return author_

    def utc_date_time_seconds_precision(self):
        return self.generator.date_time(tzinfo=datetime.timezone.utc).replace(microsecond=0)

    def temporal(self):
        opt = self.generator.random.random()
        if opt < 1 / 3:
            return sorted(
                [
                    self.utc_date_time_seconds_precision(),
                    self.utc_date_time_seconds_precision(),
                ]
            )
        elif opt < 2 / 3:
            return [self.utc_date_time_seconds_precision()] * 2
        else:
            return [self.utc_date_time_seconds_precision()]

    def link(self):
        return {"href": self.generator.uri(), "rel": self.generator.word(), "type": self.generator.mime_type()}

    def _data_request_inputs(self, unset=None):
        inputs = dict(
            id=bson.ObjectId(),
            user=self.generator.profile("username")["username"],
            title=self.generator.sentence(),
            description=(None if self.generator.pybool(30) else self.generator.paragraph()),
            authors=[self.author() for _ in range(self.generator.random.randint(1, 10))],
            geometry=self.geometry(),
            temporal=self.temporal(),
            links=[self.link() for _ in range(self.generator.random.randint(0, 10))],
            path=self.generator.file_path(),
            contact=self.generator.email(),
            additional_paths=[self.generator.file_path() for _ in range(self.generator.random.randint(0, 10))],
            variables=([] if self.generator.pybool(10) else self.generator.pylist(allowed_types=[str])),
            extra_properties=({} if self.generator.pybool(10) else self.generator.pydict(allowed_types=[str])),
        )
        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def data_request(self, unset=None, **kwargs):
        return DataRequest(**{**self._data_request_inputs(unset=unset), **kwargs})

    def data_request_public(self, unset=None, **kwargs):
        return DataRequestPublic(**{**self._data_request_inputs(unset=unset), **kwargs})

    def data_request_update(self, unset=None, **kwargs):
        return DataRequestUpdate(**{**self._data_request_inputs(unset=unset), **kwargs})


@pytest.fixture(scope="session")
def fake():
    fake_ = Faker()
    fake_.add_provider(DataRequestProvider)
    return fake_
