from collections.abc import Iterable
from itertools import zip_longest

from geojson_pydantic import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon
from geojson_pydantic.types import (
    BBox,
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)

type Geometry = LineString | MultiLineString | MultiPoint | MultiPolygon | Point | Polygon
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
