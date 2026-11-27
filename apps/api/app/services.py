from uuid import UUID

from fastapi import HTTPException, status
from app.postgres import PostgresClient as Client

from app.permissions import CATALOG_ACTIONS, has_permission
from app.repositories import (
    count_active_lakes,
    count_active_stations,
    count_visible_organizations,
    soft_delete_lake,
)
from app.repositories import get_lake_by_id as get_active_lake_by_id
from app.schemas import DashboardSummaryResponse
from domain.station_location import validate_station_inside_lake as validate_station_inside_lake

from .repositories import get_active_memberships


def get_dashboard_summary(
    database: Client, user_data: dict
) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        active_lakes_count=count_active_lakes(database),
        active_stations_count=count_active_stations(database),
        visible_organizations_count=count_visible_organizations(database, user_data),
    )


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
    # Identity creation writes the profile in the same transaction as the user.
    # Reading a profile must not create incomplete records or suppress DB errors.
    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }


def get_organization_members_for_user(
    client: Client, user_id: UUID, organization_id: UUID
) -> list[dict]:
    organization = (
        client.table("organizations")
        .select("id, name, status")
        .eq("id", str(organization_id))
        .maybe_single()
        .execute()
    )
    if not organization.data:
        raise LookupError(f"Organización no encontrada: {organization_id}")

    requester_membership = (
        client.table("memberships")
        .select("id, role, status")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if not requester_membership.data:
        raise PermissionError("Usuario no pertenece a la organización")

    response = (
        client.table("memberships")
        .select("id, user_id, role, status, created_at, updated_at")
        .eq("organization_id", str(organization_id))
        .order("created_at", desc=False)
        .execute()
    )

    members = response.data or []
    user_ids = list({str(member["user_id"]) for member in members})
    profiles = (
        client.table("profiles")
        .select("id, email, name")
        .in_("id", user_ids)
        .execute()
        .data
        if user_ids
        else []
    )
    profiles_by_id = {str(profile["id"]): profile for profile in profiles or []}

    return [
        {
            "user_id": UUID(str(member["user_id"])),
            "profile_id": UUID(str(member["user_id"])),
            "full_name": profiles_by_id.get(str(member["user_id"]), {}).get("name"),
            "email": profiles_by_id.get(str(member["user_id"]), {}).get("email"),
            "role": member["role"],
            "status": member["status"],
            "created_at": member["created_at"],
            "updated_at": member["updated_at"],
        }
        for member in members
    ]


def add_organization_member(
    database, org_id: UUID, profile_id: UUID, role: str, requester_user_id: UUID
) -> dict:
    requester_membership = (
        database.table("memberships")
        .select("role")
        .eq("organization_id", str(org_id))
        .eq("user_id", str(requester_user_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if (
        not requester_membership.data
        or requester_membership.data.get("role") != "admin"
    ):
        raise PermissionError(
            "Solo un administrador activo de la organización puede agregar miembros."
        )

    profile_res = (
        database.table("profiles").select("id").eq("id", str(profile_id)).execute()
    )
    if not profile_res.data:
        raise LookupError("Perfil inexistente")

    member_res = (
        database.table("memberships")
        .select("id")
        .eq("organization_id", str(org_id))
        .eq("user_id", str(profile_id))
        .execute()
    )
    if member_res.data:
        raise ValueError("Membresia duplicada en esta organización")

    if role == "admin":
        admin_res = (
            database.table("memberships")
            .select("id")
            .eq("user_id", str(profile_id))
            .eq("role", "admin")
            .neq("organization_id", str(org_id))
            .execute()
        )
        if admin_res.data:
            raise ValueError("El usuario ya es administrador de otra organización")

    insert_res = (
        database.table("memberships")
        .insert(
            {
                "organization_id": str(org_id),
                "user_id": str(profile_id),
                "role": role,
                "status": "active",
            }
        )
        .execute()
    )

    return insert_res.data[0]


def get_lake_by_id(database, lake_id: UUID) -> dict:
    return get_active_lake_by_id(database, lake_id)


def disable_lake(
    lake_id: UUID, current_user: dict | None = None, database=None
) -> dict:
    if not has_permission(current_user, CATALOG_ACTIONS["DISABLE"]):
        raise PermissionError("No tienes permisos para desactivar lagos.")

    if database is None:
        raise ValueError(
            "La conexión a la base de datos es requerida para desactivar un lago."
        )

    try:
        return soft_delete_lake(database, lake_id)
    except LookupError as exc:
        raise LookupError("Lago no encontrado") from exc


def create_organization(database, org_data: dict) -> dict:
    try:
        response = database.table("organizations").insert(org_data).execute()
        return response.data[0]
    except Exception as exc:
        error_msg = str(exc).lower()
        if (
            "duplicate key" in error_msg
            or "unique constraint" in error_msg
            or "23505" in error_msg
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una organización con ese identificador o nombre.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear la organización: {exc!s}",
        ) from exc


def log_audit_event(
    database,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    """Registra un evento de auditoría sin bloquear la transacción principal HTTP."""
    try:
        database.table("audit_logs").insert(
            {
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "details": details or {},
            }
        ).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Alerta: Fallo silencioso en auditoría: {e}")
