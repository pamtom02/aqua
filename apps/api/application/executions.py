import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any


async def process_scientific_job(
    job_id: str,
    config: dict[str, Any],
    update_job: Callable[[str, dict[str, Any]], None],
    timeout_seconds: float,
    execute: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    """Run a scientific job and persist its result or failure."""
    try:
        update_job(
            job_id,
            {
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
            },
        )

        result = await asyncio.wait_for(
            execute(config), timeout=timeout_seconds
        )
        update_job(
            job_id,
            {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
    except TimeoutError:
        update_job(
            job_id,
            {
                "status": "failed",
                "error_message": (
                    "Tiempo máximo de ejecución excedido "
                    f"(Timeout de {timeout_seconds}s)."
                ),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        update_job(
            job_id,
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
