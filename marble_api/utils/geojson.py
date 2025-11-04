from collections.abc import Iterable
from itertools import zip_longest

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
from geojson_pydantic.types import (
    BBox,
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)

# Note: STAC Geometry differs from the GeoJSON Geometry definition (GeometryCollection not included)
type Geometry = LineString | MultiLineString | MultiPoint | MultiPolygon | Point | Polygon
type GeoJSON = Geometry | FeatureCollection | Feature | GeometryCollection
type Coordinates = (
    LineStringCoords | MultiLineStringCoords | MultiPointCoords | MultiPolygonCoords | PolygonCoords | Position
)


def _coordinates_to_points(coordinates: Coordinates) -> Iterable[Position]:
    if isinstance(coordinates[0], Iterable):
        for coord in coordinates:
            yield from _coordinates_to_points(coord)
    else:
        yield coordinates


def bbox_from_coordinates(coordinates: Coordinates) -> BBox:
    """Return a bounding box from a set of coordinates."""
    min_max = []
    for values in zip_longest(*_coordinates_to_points(coordinates)):
        real_values = [v or 0 for v in values]  # coordinates without elevation are considered to be at elevation 0
        min_max.append((min(real_values), max(real_values)))
    return [v for val in min_max for v in val]


def _validate_geometries(geometries: list[Geometry], geojson_type: str) -> None:
    geometry_types = frozenset({geo.type for geo in geometries})
    if len(geometry_types) != 1 and geometry_types not in {
        frozenset(),
        frozenset(("Point", "MultiPoint")),
        frozenset(("LineString", "MultiLineString")),
        frozenset(("Polygon", "MultiPolygon")),
    }:
        raise ValueError(f"GeoJSON of type '{geojson_type}' is not convertable to a STAC compliant geometry.")


def _extract_geometries(geojson: GeoJSON | None) -> list[Geometry]:
    """Return all geometries present in the geojson as a flat list."""
    if geojson.type == "FeatureCollection":
        return [geo for feature in geojson.features for geo in _extract_geometries(feature.geometry) if geo]
    if geojson.type == "GeometryCollection":
        return geojson.geometries
    if geojson.type == "Feature":
        return _extract_geometries(geojson.geometry)
    if geojson is None:
        return []
    return [geojson]


def validate_collapsible(geojson: GeoJSON) -> None:
    """Raise a ValueError if the geojson cannot be collapsed to a STAC compatible geometry."""
    _validate_geometries(_extract_geometries(geojson), geojson.type)


def collapse_geometries(geojson: GeoJSON, check: bool = True) -> Geometry | None:
    """
    Return a single geometry that represents the same geo-spatial data as the geojson.

    This will collapse Features, FeatureCollections, and GeometryCollections into other
    geometry types that represent the same points, lines, or polygons. The converted geometries
    are compatible with STAC.

    If check is False, this will not validate that the geojson can be collapsed before attempting
    to collapse it. This may result in undefined behaviour. It is strongly recommended that you
    call validate_collapsible(geojson) prior to calling this function with check=False.
    """
    geometries = _extract_geometries(geojson)
    if check:
        _validate_geometries(geometries, geojson.type)
    if not geometries:
        return None
    if len(geometries) == 1:
        return geometries[0]
    coordinates = []
    for geo in geometries:
        if geo.type in ("Point", "LineString", "Polygon"):
            coordinates.append(geo.coordinates)
        else:
            coordinates.extend(geo.coordinates)
        if geo.type in ("Point", "MultiPoint"):
            geo_type = MultiPoint
        elif geo.type in ("LineString", "MultiLineString"):
            geo_type = MultiLineString
        else:
            geo_type = MultiPolygon
    return geo_type(coordinates=coordinates, type=geo_type.__name__)
