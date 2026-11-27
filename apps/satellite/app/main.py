from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.infrastructure.queueing import enqueue_measurement_summary, get_redis_client
from app.application.measurements import predict_baseline, submit_summary

app = FastAPI(
    title=settings.service_name,
    description="Servicio Satellite para encolar trabajos científicos.",
    version="v1",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Parámetros de entrada inválidos."},
    )


class MeasurementSummaryRequest(BaseModel):
    measurements: list[Annotated[float, Field(allow_inf_nan=False)]] = Field(
        min_length=1,
        max_length=10000,
    )


class EnqueuedTaskResponse(BaseModel):
    task_id: str
    status: str


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health", tags=["System"])
def health_check(
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> dict[str, str]:
    try:
        redis_client.ping()
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis no está disponible.",
        ) from exc

    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "status": "ok",
        "queue": "connected",
    }


@app.post(
    "/tasks/measurement-summary",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EnqueuedTaskResponse,
)
def enqueue_summary(
    request: MeasurementSummaryRequest,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> EnqueuedTaskResponse:
    try:
        task_id = submit_summary(
            request.measurements,
            lambda values: enqueue_measurement_summary(values, redis_client),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo encolar la tarea científica en Redis.",
        ) from exc

    return EnqueuedTaskResponse(task_id=task_id, status="queued")

class BaselineRequest(BaseModel):
    y_train: list[float]
    num_predictions: int

class BaselineResponse(BaseModel):
    predictions: list[float]

@app.post("/api/v1/baseline", response_model=BaselineResponse)
def run_baseline(payload: BaselineRequest):
    try:
        predictions = predict_baseline(payload.y_train, payload.num_predictions)
        return BaselineResponse(predictions=predictions)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Even if Kubero requires a domain, processing endpoints remain private.
@app.middleware("http")
async def internal_access(request, call_next):
    import os
    import secrets
    from starlette.responses import JSONResponse
    if request.url.path not in {"/", "/health", "/api/v1/health"} and settings.environment == "production":
        expected = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
        received = request.headers.get("X-Internal-Token", "")
        if len(expected) < 32:
            return JSONResponse(status_code=503, content={"detail": "Autenticación interna sin configurar."})
        if not secrets.compare_digest(expected, received):
            return JSONResponse(status_code=401, content={"detail": "Autenticación interna requerida."})
    return await call_next(request)
