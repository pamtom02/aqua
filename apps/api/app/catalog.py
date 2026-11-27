import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_catalog_create_permission
from app.database import database

from application.stations import (
    StationConflict,
    StationLakeMissing,
    StationStoreUnavailable,
    create_station as create_catalog_station,
)
from catalog.application.schemas import StationCreate
from infrastructure.stations import PostgresStations

router = APIRouter()


@router.post(
    "/api/v1/lakes/{lake_id}/stations",
    status_code=201,
    dependencies=[Depends(require_catalog_create_permission)],
)
def create_station(lake_id: uuid.UUID, payload: StationCreate):
    try:
        station = create_catalog_station(
            PostgresStations(database),
            str(lake_id),
            payload.latitude,
            payload.longitude,
            {
                "code": payload.code,
                "name": payload.name,
                "description": payload.description,
                "status": payload.status or "active",
            },
        )
    except StationLakeMissing as exc:
        raise HTTPException(status_code=404, detail="El lago asociado no existe.") from exc
    except StationConflict as exc:
        raise HTTPException(
            status_code=409, detail="El código de la estación ya existe para este lago."
        ) from exc
    except StationStoreUnavailable as exc:
        raise HTTPException(
            status_code=500, detail="Error al crear la estación en la base de datos."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": station.get("id"), "message": "Estación creada exitosamente."}
