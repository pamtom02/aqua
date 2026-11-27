from uuid import UUID


class PostgresPreparedInputs:
    def __init__(self, client):
        self.client = client

    def original_exists(self, import_id: UUID) -> bool:
        response = self.client.table("imports").select("id").eq(
            "id", str(import_id)
        ).limit(1).execute()
        return bool(getattr(response, "data", None))

    def add(self, fields: dict) -> dict | None:
        response = self.client.table("prepared_inputs").insert(fields).execute()
        rows = getattr(response, "data", None)
        return rows[0] if rows else None
