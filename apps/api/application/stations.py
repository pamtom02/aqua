from typing import Protocol

from domain.station_location import validate_station_inside_lake


class StationConflict(Exception):
    pass


class StationLakeMissing(Exception):
    pass


class StationStoreUnavailable(Exception):
    pass


class Stations(Protocol):
    def find_lake(self, lake_id: str) -> dict | None: ...
    def exists(self, lake_id: str, code: str) -> bool: ...
    def add(self, fields: dict) -> dict: ...


def create_station(
    stations: Stations, lake_id: str, latitude: float, longitude: float, fields: dict
) -> dict:
    lake = stations.find_lake(lake_id)
    if lake is None:
        raise StationLakeMissing
    if lake.get("geom"):
        validate_station_inside_lake(lake["geom"], latitude, longitude)
    if stations.exists(lake_id, fields["code"]):
        raise StationConflict
    return stations.add({
        **fields,
        "lake_id": lake_id,
        "point": f"POINT({longitude} {latitude})",
    })
