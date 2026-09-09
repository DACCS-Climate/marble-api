import pytest
from faker import Faker
from geojson_pydantic import (
    Feature,
    FeatureCollection,
    GeometryCollection,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
)

from marble_api.utils.geojson import bbox_from_coordinates, collapse_geometries, validate_collapsible


@pytest.fixture(scope="session")
def fake(faker_providers) -> Faker:
    fake_ = Faker()
    fake_.add_provider(faker_providers["GeoJsonProvider"])
    return fake_


class TestBboxFromCoordinates:
    def test_2d_point(self):
        assert bbox_from_coordinates([1, 2]) == [1, 1, 2, 2]

    def test_3d_point(self):
        assert bbox_from_coordinates([1, 2, 3]) == [1, 1, 2, 2, 3, 3]

    def test_2d_line(self):
        assert bbox_from_coordinates([[1, 2], [-1, -3]]) == [-1, 1, -3, 2]

    def test_3d_line(self):
        assert bbox_from_coordinates([[1, 2, 4], [-1, -3, 33]]) == [-1, 1, -3, 2, 4, 33]

    def test_mixed_d_line(self):
        assert bbox_from_coordinates([[1, 2], [-1, -3, 33]]) == [-1, 1, -3, 2, 0, 33]

    def test_deeply_nested(self):
        assert bbox_from_coordinates([[[[1, 2], [-1, -3, 33]]]]) == [-1, 1, -3, 2, 0, 33]

    def test_different_nested(self):
        assert bbox_from_coordinates([[1, 2], [[[-1, -3, 33]]]]) == [-1, 1, -3, 2, 0, 33]


@pytest.mark.parametrize("dimensions", [2, 3])
class TestValidateCollapsible:
    def test_collapsible(self, fake, dimensions):
        errors = []
        for geo in fake.collapsible_geojsons(dimensions):
            try:
                validate_collapsible(geo)
            except ValueError:
                errors.append(geo)
        assert not errors, "These geojsons should be collapsible but weren't properly collapsed"

    def test_uncollapsible(self, fake, dimensions):
        errors = []
        for geo in fake.uncollapsible_geojsons(dimensions):
            try:
                validate_collapsible(geo)
            except ValueError:
                pass
            else:
                errors.append(geo)
        assert not errors, "These geojsons should be uncollapsible but were properly collapsed"


@pytest.mark.parametrize("dimensions", [2, 3])
class TestCollapseGeometries:
    def test_no_change_to_stac_geometries(self, fake, dimensions):
        geometries = fake.stac_geometries(dimensions)
        assert [collapse_geometries(geo) for geo in geometries] == geometries

    def test_cannot_collapse_uncollapsible(self, fake, dimensions):
        for geo in fake.uncollapsible_geojsons(dimensions):
            with pytest.raises(ValueError):
                collapse_geometries(geo)

    def test_collapsible_geojson_changed(self, fake, dimensions):
        not_changed = []
        stac_geometry_types = [geo.type for geo in fake.stac_geometries()]
        for geo in fake.collapsible_geojsons(dimensions):
            if geo.type not in stac_geometry_types:
                if collapse_geometries(geo) == geo:
                    not_changed.append(geo)
        assert not not_changed, "These geojsons should have been collapsed/changed but they weren't"

    def test_feature_changed(self, fake, dimensions):
        not_changed = []
        for feat in fake.collapsible_features(dimensions):
            if feat.geometry.type != "GeometryCollection":
                if collapse_geometries(feat) != feat.geometry:
                    not_changed.append(feat)
        assert not not_changed, "These features should have been collapsed to their geometry but they weren't"

    @pytest.mark.parametrize(
        "geometries",
        [
            {"geos": ["point", "multipoint"], "result": MultiPoint},
            {"geos": ["linestring", "multilinestring"], "result": MultiLineString},
            {"geos": ["polygon", "multipolygon"], "result": MultiPolygon},
        ],
        ids=lambda val: val["result"].__name__,
    )
    @pytest.mark.parametrize(
        "geo_factory",
        [
            (
                "GeometryCollection(Geometry)",
                lambda geos: GeometryCollection(type="GeometryCollection", geometries=geos),
            ),
            (
                "Feature(GeometryCollection(Geometry))",
                lambda geos: Feature(
                    type="Feature",
                    properties={},
                    geometry=GeometryCollection(type="GeometryCollection", geometries=geos),
                ),
            ),
            (
                "FeatureCollection(Feature(GeometryCollection(Geometry)))",
                lambda geos: FeatureCollection(
                    type="FeatureCollection",
                    features=[
                        Feature(
                            type="Feature",
                            properties={},
                            geometry=GeometryCollection(type="GeometryCollection", geometries=geos),
                        )
                    ],
                ),
            ),
            (
                "FeatureCollection(Feature(Geometry))",
                lambda geos: FeatureCollection(
                    type="FeatureCollection",
                    features=[
                        Feature(
                            type="Feature",
                            properties={},
                            geometry=geo,
                        )
                        for geo in geos
                    ],
                ),
            ),
        ],
        ids=lambda val: val[0],
    )
    def test_complex_collapsible(self, fake, dimensions, geometries, geo_factory):
        geos = [getattr(fake, f"geo_{geo}")(dimensions) for geo in geometries["geos"]]
        result = geometries["result"]
        factory_name, factory = geo_factory
        assert collapse_geometries(factory(geos)) == result(
            type=result.__name__, coordinates=[geos[0].coordinates, *geos[1].coordinates]
        ), f"Unable to collapse {factory_name} into a {result.__name__}"
