from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status

from app.auth import verify_access_token
from app.database import database
from app.dependencies import require_admin
from app.schemas import (
    MembershipCreate,
    OrganizationCreate,
    OrganizationMemberResponse,
    OrganizationOut,
    ProfileOption,
    UserOrganizationResponse,
)
from app.services import (
    add_organization_member,
    create_organization,
    get_organization_members_for_user,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.get("/profiles", response_model=list[ProfileOption])
def list_profiles_for_members(payload: dict = Depends(require_admin)):  # noqa: B008
    response = (
        database.table("profiles").select("id, email, name").order("name").execute()
    )
    return response.data or []


@router.get("/", response_model=list[UserOrganizationResponse])
def get_user_organizations(payload: dict = Depends(verify_access_token)):  # noqa: B008
    """Recupera las organizaciones exclusivas del usuario autenticado."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario no encontrado en el token.",
        )

    try:
        response = (
            database.table("memberships")
            .select("role, organizations!inner(id, name)")
            .eq("user_id", user_id)
            .execute()
        )

        organizations_list = []
        for item in response.data:
            org_data = item.get("organizations", {})
            organizations_list.append(
                {
                    "id": org_data.get("id"),
                    "name": org_data.get("name"),
                    "role": item.get("role"),
                }
            )

        return organizations_list

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al recuperar organizaciones: {exc}",
        ) from exc


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
)
def list_organization_members(
    organization_id: UUID,
    payload: dict = Security(verify_access_token),  # noqa: B008
):
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticación no está disponible",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )

    current_user_id = UUID(str(user_id))

    try:
        members = get_organization_members_for_user(
            database, current_user_id, organization_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return members


@router.post("/{id}/members")
def create_organization_member(
    id: UUID,
    membership: MembershipCreate,
    payload: dict = Depends(verify_access_token),  # noqa: B008
):
    try:
        return add_organization_member(
            database=database,
            org_id=id,
            profile_id=membership.profile_id,
            role=membership.role,
            requester_user_id=UUID(str(payload["sub"])),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_org(
    org: OrganizationCreate,
    payload: dict = Depends(require_admin),  # noqa: B008
):
    org_data = {
        "name": org.name,
        "identifier": org.identifier,
        "description": org.description,
        "status": "active",
    }
    organization = create_organization(database, org_data)
    database.table("memberships").insert(
        {
            "organization_id": str(organization["id"]),
            "user_id": str(payload["sub"]),
            "role": "admin",
            "status": "active",
        }
    ).execute()
    return organization
