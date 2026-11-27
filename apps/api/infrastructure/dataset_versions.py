from uuid import UUID


def find_training_version(client, version_id: UUID) -> dict | None:
    response = (
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, state, status")
        .eq("id", str(version_id))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
