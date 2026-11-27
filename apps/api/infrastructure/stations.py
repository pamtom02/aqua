from app.postgres import APIError

from application.stations import StationConflict, StationStoreUnavailable


class PostgresStations:
    def __init__(self, client):
        self.client = client

    def find_lake(self, lake_id: str) -> dict | None:
        rows = self.client.table("lakes").select("id, geom").eq("id", lake_id).execute().data
        return rows[0] if rows else None

    def exists(self, lake_id: str, code: str) -> bool:
        return bool(self.client.table("stations").select("id").eq(
            "lake_id", lake_id
        ).eq("code", code).execute().data)

    def add(self, fields: dict) -> dict:
        try:
            rows = self.client.table("stations").insert(fields).execute().data
        except APIError as exc:
            if exc.code == "23505":
                raise StationConflict from exc
            raise
        if not rows:
            raise StationStoreUnavailable
        return rows[0]
