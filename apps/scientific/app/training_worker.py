"""Consume trabajos de entrenamiento persistidos en PostgreSQL."""

import logging
import os
import time
from functools import partial

import httpx
from app.postgres import PostgresClient

from app.application.training import run_training
from app.config import settings
from app.infrastructure.training import PostgresTrainingJobs, download_training_file

logger = logging.getLogger(__name__)


def run_one(database, core: httpx.Client) -> bool:
    return run_training(PostgresTrainingJobs(database), partial(download_training_file, core))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    database = PostgresClient(os.environ["DATABASE_URL"])
    with httpx.Client(
        base_url=settings.core_api_url,
        headers={"X-Internal-Token": os.environ["INTERNAL_SERVICE_TOKEN"]},
        timeout=15,
    ) as core:
        while True:
            try:
                if run_one(database, core):
                    continue
            except Exception:
                logger.exception("Fallo al procesar la cola de entrenamiento.")
            time.sleep(2)


if __name__ == "__main__":
    main()
