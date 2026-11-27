from shapely import from_wkt
from shapely.geometry import Point, shape


def validate_station_inside_lake(lake_geojson: dict | str, lat: float, lon: float) -> None:
    if lake_geojson is None:
        raise ValueError("La geometría del lago no es válida.")

    try:
        if isinstance(lake_geojson, str):
            lake_polygon = from_wkt(lake_geojson.strip())
        else:
            lake_polygon = shape(lake_geojson)
    except Exception as exc:
        raise ValueError("La geometría del lago no es válida.") from exc

    station_point = Point(lon, lat)
    if not lake_polygon.covers(station_point):
        raise ValueError(
            "Las coordenadas de la estación están fuera del polígono del lago."
        )
