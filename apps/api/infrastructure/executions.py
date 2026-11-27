from typing import Any
from uuid import UUID


def find_job(
    client, *, organization_id: UUID, idempotency_key: str
) -> dict[str, Any] | None:
    result = (
        client.schema("scientific")
        .table("jobs")
        .select("*")
        .eq("organization_id", str(organization_id))
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    return result.data[0] if getattr(result, "data", None) else None


def update_job(client, job_id: str, fields: dict[str, Any]) -> None:
    client.schema("scientific").table("jobs").update(fields).eq("id", job_id).execute()


def insert_job(client, fields: dict[str, Any]) -> dict | None:
    response = client.schema("scientific").table("jobs").insert(fields).execute()
    rows = getattr(response, "data", None)
    return rows[0] if rows else None
