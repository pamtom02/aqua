import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.pilot import train_pilot


@dataclass(frozen=True)
class TrainingJob:
    id: str
    version_id: str


class TrainingJobs(Protocol):
    def claim(self) -> TrainingJob | None: ...
    def finish(self, job: TrainingJob, outcome: dict) -> None: ...


def run_training(
    jobs: TrainingJobs, download: Callable[[str], tuple[bytes, str | None]]
) -> bool:
    job = jobs.claim()
    if job is None:
        return False
    try:
        data, checksum = download(job.id)
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError("El checksum del archivo de entrenamiento no coincide.")
        outcome = {"status": "completed", "result": train_pilot(data, UUID(job.version_id))}
    except ValueError as exc:
        outcome = {"status": "failed", "error_message": str(exc)}
    jobs.finish(job, outcome)
    return True
