import bson
import pytest
from faker import Faker
from faker.providers import BaseProvider
from geojson_pydantic import (
    Feature,
    FeatureCollection,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

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
        return Point(type="Point", coordinates=self.point(dimensions), **self._geo_base())

    def geo_multipoint(self, dimensions=None):
        return MultiPoint(
            type="MultiPoint",
            coordinates=[self.point(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
            **self._geo_base(),
        )

    def geo_linestring(self, dimensions=None):
        return LineString(type="LineString", coordinates=self.line(dimensions), **self._geo_base())

    def geo_multilinestring(self, dimensions=None):
        return MultiLineString(
            type="MultiLineString",
            coordinates=[self.line(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
            **self._geo_base(),
        )

    def geo_polygon(self, dimensions=None):
        return Polygon(type="Polygon", coordinates=[self.linear_ring(dimensions)], **self._geo_base())

    def geo_multipolygon(self, dimensions=None):
        return MultiPolygon(
            type="MultiPolygon",
            coordinates=[
                [self.linear_ring(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))]
            ],
            **self._geo_base(),
        )

    def stac_geometries(self, dimensions=None):
        return [
            self.geo_point(dimensions=dimensions),
            self.geo_multipoint(dimensions=dimensions),
            self.geo_linestring(dimensions=dimensions),
            self.geo_multilinestring(dimensions=dimensions),
            self.geo_polygon(dimensions=dimensions),
            self.geo_multipolygon(dimensions=dimensions),
        ]

    def collapsible_geometry_combos(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        return [
            combo
            for i in range(0, len(stac_geometries), 2)
            for combo in ([stac_geometries[i]], [stac_geometries[i + 1]], stac_geometries[i : i + 2])
        ]

    def uncollapsible_geometry_combos(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        combos = []
        for i in range(0, len(stac_geometries), 2):
            for j in range(i + 2, len(stac_geometries)):
                combos.append([stac_geometries[i], stac_geometries[j]])
                combos.append([stac_geometries[i + 1], stac_geometries[j]])
        return combos

    def collapsible_geometry_collections(self, dimensions=None):
        collapsible_geometry_combos = self.collapsible_geometry_combos(dimensions=dimensions)
        return [
            GeometryCollection(type="GeometryCollection", geometries=geos)
            for geos in collapsible_geometry_combos
            if len(geos) > 1
        ]

    def uncollapsible_geometry_collections(self, dimensions=None):
        uncollapsible_geometry_combos = self.uncollapsible_geometry_combos(dimensions=dimensions)
        return [
            GeometryCollection(type="GeometryCollection", geometries=geos) for geos in uncollapsible_geometry_combos
        ]

    def collapsible_features(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        collapsible_geometry_collections = self.collapsible_geometry_collections(dimensions=dimensions)
        return [
            Feature(type="Feature", geometry=geo, properties={})
            for geo in stac_geometries + collapsible_geometry_collections
        ]

    def uncollapsible_features(self, dimensions=None):
        uncollapsible_geometry_collections = self.uncollapsible_geometry_collections(dimensions=dimensions)
        return [Feature(type="Feature", geometry=geo, properties={}) for geo in uncollapsible_geometry_collections]

    def collapsible_feature_collections(self, dimensions=None):
        collapsible_geometry_combos = self.collapsible_geometry_combos(dimensions=dimensions)
        collapsible_features = self.collapsible_features(dimensions=dimensions)
        collections = []
        for combo in collapsible_geometry_combos:
            collections.append(
                FeatureCollection(
                    type="FeatureCollection",
                    features=[Feature(type="Feature", geometry=geo, properties={}) for geo in combo],
                )
            )
        for feature in collapsible_features:
            collections.append(FeatureCollection(type="FeatureCollection", features=[feature]))
        return collections

    def uncollapsible_feature_collections(self, dimensions=None):
        uncollapsible_geometry_combos = self.uncollapsible_geometry_combos(dimensions=dimensions)
        uncollapsible_features = self.uncollapsible_features(dimensions=dimensions)
        collections = []
        for combo in uncollapsible_geometry_combos:
            collections.append(
                FeatureCollection(
                    type="FeatureCollection",
                    features=[Feature(type="Feature", geometry=geo, properties={}) for geo in combo],
                )
            )
        for feature in uncollapsible_features:
            collections.append(FeatureCollection(type="FeatureCollection", features=[feature]))
        return collections

    def collapsible_geojsons(self, dimensions=None):
        return (
            self.stac_geometries(dimensions=dimensions)
            + self.collapsible_geometry_collections(dimensions=dimensions)
            + self.collapsible_feature_collections(dimensions=dimensions)
        )

    def uncollapsible_geojsons(self, dimensions=None):
        return self.uncollapsible_geometry_collections(dimensions=dimensions) + self.uncollapsible_feature_collections(
            dimensions=dimensions
        )

    def collapsible_geojson(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.random.choice([3, 2])
        return self.generator.random.choice(self.collapsible_geojsons(dimensions))

    def uncollapsible_geojson(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.random.choice([3, 2])
        return self.generator.random.choice(self.uncollapsible_geojsons(dimensions))


class DataRequestProvider(GeoJsonProvider):
    def author(self):
        author_ = {"last_name": self.generator.last_name()}
        if self.generator.pybool():
            author_["first_name"] = self.generator.first_name()
        if self.generator.pybool():
            author_["email"] = self.generator.email()
        return author_

    def tz_aware_date_time_seconds_precision(self):
        return self.generator.date_time(tzinfo=self.generator.pytimezone()).replace(microsecond=0)

    def temporal(self):
        opt = self.generator.random.random()
        if opt < 1 / 3:
            return sorted(
                [
                    self.tz_aware_date_time_seconds_precision(),
                    self.tz_aware_date_time_seconds_precision(),
                ]
            )
        elif opt < 2 / 3:
            return [self.tz_aware_date_time_seconds_precision()] * 2
        else:
            return [self.tz_aware_date_time_seconds_precision()]

    def link(self):
        return {"href": self.generator.uri(), "rel": self.generator.word(), "type": self.generator.mime_type()}

    def _data_request_inputs(self, unset=None):
        inputs = dict(
            id=bson.ObjectId(),
            user=self.generator.profile("username")["username"],
            title=self.generator.sentence(),
            description=(None if self.generator.pybool(30) else self.generator.paragraph()),
            authors=[self.author() for _ in range(self.generator.random.randint(1, 10))],
            geometry=self.collapsible_geojson(),
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
