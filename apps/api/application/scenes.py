from datetime import date
from typing import Protocol
from uuid import UUID


class SceneAlreadyRegistered(Exception):
    pass


class SceneLakeMissing(Exception):
    pass


class SceneStoreUnavailable(Exception):
    pass


class SceneRepository(Protocol):
    def add(self, scene: dict) -> dict: ...


def register_scene(
    repository: SceneRepository, lake_id: UUID, identifier: str, acquired_on: date
) -> dict:
    return repository.add({
        "lake_id": str(lake_id),
        "scene_identifier": identifier,
        "acquisition_date": acquired_on.isoformat(),
        "metadata": {"provider": "Sentinel-2 L2A"},
    })
