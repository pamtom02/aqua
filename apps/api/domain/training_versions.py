from uuid import UUID


class TrainingVersionMissing(Exception):
    pass


class TrainingVersionMismatch(Exception):
    pass


class TrainingVersionUnpublished(Exception):
    pass


def require_published_version(version: dict | None, dataset_id: UUID) -> None:
    if version is None:
        raise TrainingVersionMissing
    if str(version.get("dataset_id")) != str(dataset_id):
        raise TrainingVersionMismatch
    if str(version.get("state") or version.get("status")).upper() != "PUBLISHED":
        raise TrainingVersionUnpublished
