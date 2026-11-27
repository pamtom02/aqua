from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from app.postgres import APIError

from app.auth import verify_access_token
from app.database import database
from application.ingestion import OriginalImportMissing, PreparedInputNotStored, prepare_input
from infrastructure.ingestion import PostgresPreparedInputs

from ingestion.application.schemas import PreparedInputCreate, PreparedInputResponse

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


def _raise_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if str(error_code) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un insumo registrado para esta clave de origen.",
        ) from exc
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo registrar el insumo preparado.",
    ) from exc


@router.post(
    "/prepared",
    response_model=PreparedInputResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prepared_input(
    prepared_input: PreparedInputCreate,
    _user: Annotated[dict, Depends(verify_access_token)],
):
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        return prepare_input(
            PostgresPreparedInputs(database),
            prepared_input.original_import_id,
            prepared_input.source_key,
            prepared_input.metadata,
        )
    except OriginalImportMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        ) from exc
    except PreparedInputNotStored as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el insumo preparado.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)
