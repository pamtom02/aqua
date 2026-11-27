import logging
from datetime import UTC, datetime

import httpx

from app.application.training import TrainingJob

logger = logging.getLogger(__name__)


class PostgresTrainingJobs:
    def __init__(self, database):
        self.database = database

    @property
    def jobs(self):
        return self.database.schema("scientific").table("jobs")

    def claim(self) -> TrainingJob | None:
        queued = (
            self.jobs.select("id").eq("job_type", "training").eq("status", "queued")
            .order("created_at").limit(1).execute().data
        )
        if not queued:
            return None
        job_id = queued[0]["id"]
        claimed = (
            self.jobs.update({"status": "running", "started_at": datetime.now(UTC).isoformat()})
            .eq("id", job_id).eq("status", "queued").execute().data
        )
        if not claimed:
            return None
        return TrainingJob(job_id, (claimed[0].get("config") or {}).get("version_id") or "")

    def finish(self, job: TrainingJob, outcome: dict) -> None:
        self.jobs.update({**outcome, "completed_at": datetime.now(UTC).isoformat()}).eq(
            "id", job.id
        ).eq("status", "running").execute()


def download_training_file(core: httpx.Client, job_id: str) -> tuple[bytes, str | None]:
    try:
        with core.stream("GET", f"/api/v1/datasets/training-jobs/{job_id}/file") as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 1024 * 1024:
                    raise ValueError("El CSV de entrenamiento supera 1 MiB.")
            return bytes(data), response.headers.get("X-Content-SHA256")
    except httpx.HTTPError as exc:
        logger.exception("No se pudo obtener el CSV del trabajo %s", job_id)
        raise ValueError("No se pudo obtener el CSV publicado desde Core.") from exc
