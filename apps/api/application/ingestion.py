from typing import Protocol
from uuid import UUID


class OriginalImportMissing(Exception):
    pass


class PreparedInputNotStored(Exception):
    pass


class PreparedInputs(Protocol):
    def original_exists(self, import_id: UUID) -> bool: ...
    def add(self, fields: dict) -> dict | None: ...


def prepare_input(
    store: PreparedInputs, import_id: UUID, source_key: str, metadata: dict
) -> dict:
    if not store.original_exists(import_id):
        raise OriginalImportMissing
    result = store.add({
        "original_import_id": str(import_id),
        "source_key": source_key,
        "metadata": metadata,
    })
    if result is None:
        raise PreparedInputNotStored
    return result
