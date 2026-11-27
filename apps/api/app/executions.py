from functools import partial
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    status,
)
from app.postgres import APIError

from app.auth import verify_access_token
from app.database import database
from app.dependencies import require_internal_service
from application.executions import process_scientific_job
from domain.execution.schemas import JobCreate, JobResponse, JobStatus, TrainingConfig
from domain.training_versions import (
    TrainingVersionMismatch, TrainingVersionMissing, TrainingVersionUnpublished,
    require_published_version,
)
from infrastructure.dataset_versions import find_training_version
from infrastructure.execution_simulator import simulate_execution
from infrastructure.executions import find_job, insert_job, update_job

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

JOB_TIMEOUT_SECONDS = 10.0


def _require_database():
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )
    return database


def _validate_training_version(client, config: TrainingConfig) -> None:
    try:
        version = find_training_version(client, config.version_id)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    try:
        require_published_version(version, config.dataset_id)
    except TrainingVersionMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la versión del dataset.",
        ) from exc
    except TrainingVersionMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La versión no pertenece al dataset indicado.",
        ) from exc
    except TrainingVersionUnpublished as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden entrenar versiones publicadas.",
        ) from exc


def _matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return (
        job.get("job_type") == payload.job_type
        and job.get("organization_id") == str(payload.organization_id)
        and job.get("config") == config
    )


def _job_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = UUID(str(job["id"]))
    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
    }


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    description=(
        "Devuelve el estado de un trabajo solo si el usuario autenticado "
        "pertenece activamente a la organización propietaria."
    ),
)
def get_job_status(
    job_id: UUID,
    payload: Annotated[dict, Depends(verify_access_token)],
) -> JobStatus:
    client = _require_database()

    try:
        response = (
            client.schema("scientific").table("jobs")
            .select(
                "id, organization_id, job_type, status, config, result, "
                "dataset_version_id, model_version_id, requested_by, "
                "error_message, created_at, started_at, completed_at, updated_at"
            )
            .eq("id", str(job_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    rows = getattr(response, "data", None) if response else None
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    job = rows[0]
    organization_id = job.get("organization_id")
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    try:
        user_id = str(UUID(str(payload.get("sub"))))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc

    try:
        membership = (
            client.table("memberships")
            .select("id")
            .eq("user_id", user_id)
            .eq("organization_id", str(organization_id))
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not getattr(membership, "data", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No perteneces a la organización propietaria del trabajo.",
        )

    return job


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    x_idempotency_key: str | None = Header(
        default=None, alias="X-Idempotency-Key", max_length=255
    ),
) -> JobResponse:
    client = _require_database()
    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None
    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    if payload.job_type == "training":
        _validate_training_version(client, payload.config)

    config = payload.config.model_dump(mode="json")
    if idempotency_key is not None:
        existing_job = find_job(
            client, organization_id=payload.organization_id, idempotency_key=idempotency_key
        )
        if existing_job is not None:
            if _matches_request(existing_job, payload, config):
                return _job_response(existing_job)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La clave de idempotencia ya fue utilizada "
                    "con un contenido diferente."
                ),
            )

    db_payload = {
        "job_type": payload.job_type,
        "organization_id": str(payload.organization_id),
        "config": config,
        "status": "queued",
    }
    if isinstance(payload.config, TrainingConfig):
        db_payload["dataset_version_id"] = str(payload.config.version_id)
    if idempotency_key is not None:
        db_payload["idempotency_key"] = idempotency_key

    try:
        inserted_job = insert_job(client, db_payload)
    except APIError as exc:
        if exc.code == "23505" and idempotency_key is not None:
            existing_job = find_job(
                client, organization_id=payload.organization_id, idempotency_key=idempotency_key
            )
            if existing_job is not None:
                if _matches_request(existing_job, payload, config):
                    return _job_response(existing_job)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "La clave de idempotencia ya fue utilizada "
                        "con un contenido diferente."
                    ),
                ) from exc
        _raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if inserted_job is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo persistir el trabajo.",
        )

    if payload.job_type != "training":
        background_tasks.add_task(
            process_scientific_job,
            str(inserted_job["id"]),
            config,
            partial(update_job, client),
            JOB_TIMEOUT_SECONDS,
            simulate_execution,
        )
    return _job_response(inserted_job)


def _raise_database_error(exc: Exception) -> None:
    error_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la organización asociada al trabajo.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación del trabajo.",
    ) from exc
