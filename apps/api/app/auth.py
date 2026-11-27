"""Local identity, revocable sessions and JWT validation backed by PostgreSQL."""
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.config import settings
from app.database import database
from app.passwords import hash_password, validate_password, verify_password
from app.permissions import CATALOG_ACTIONS, has_permission
from app.second_factor import consume_second_factor

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)
DUMMY_PASSWORD_HASH = hash_password("non-account-password", b"aquabloom-dummy01")


class AuthException(Exception):
    def __init__(self, message: str, details: dict):
        self.message, self.details = message, details


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr
    second_factor: SecretStr | None = None

    @field_validator("second_factor")
    @classmethod
    def second_factor_size(cls, value):
        if value is not None and not 6 <= len(value.get_secret_value()) <= 64:
            raise ValueError("Segundo factor no válido.")
        return value

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Correo no válido.")
        return value

    @field_validator("password")
    @classmethod
    def password_size(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 256:
            raise ValueError("Contraseña no válida.")
        return value


class RegisterInput(LoginInput):
    full_name: str = Field(min_length=1, max_length=200)


class RefreshInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    status: str


class MembershipResponse(BaseModel):
    id: UUID
    role: str
    status: str
    organization: OrganizationResponse


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str | None
    memberships: list[MembershipResponse]


def require_database():
    if database is None:
        raise HTTPException(503, "PostgreSQL sin configurar.")
    return database


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(email, password, name, role="auditor"):
    validate_password(password)
    user_id = str(uuid4())
    encoded = hash_password(password)
    with require_database().connection() as connection:
        user = connection.execute(
            """INSERT INTO public.users(id,email,password_hash,role)
               VALUES(%s,%s,%s,%s) RETURNING id,email,role""",
            (user_id, email.strip().lower(), encoded, role),
        ).fetchone()
        connection.execute(
            "INSERT INTO public.profiles(id,email,name) VALUES(%s,%s,%s)",
            (user_id, email.strip().lower(), name),
        )
    return user


def _rate_limit(request, email):
    # Do not trust X-Forwarded-For supplied by an arbitrary HTTP caller.
    peer = request.client.host if request.client else "unknown"
    keys = [digest("account:" + email), digest("peer:" + peer)]
    with require_database().connection() as connection:
        for key, limit in zip(keys, (10, 100)):
            row = connection.execute(
                """INSERT INTO public.login_attempts(key,attempts,window_start)
                   VALUES(%s,1,now()) ON CONFLICT(key) DO UPDATE SET
                   attempts=CASE WHEN login_attempts.window_start < now()-interval '15 minutes'
                                 THEN 1 ELSE login_attempts.attempts+1 END,
                   window_start=CASE WHEN login_attempts.window_start < now()-interval '15 minutes'
                                     THEN now() ELSE login_attempts.window_start END
                   RETURNING attempts""", (key,),
            ).fetchone()
            if row["attempts"] > limit:
                # Commit the consumed attempt before returning an error.
                connection.commit()
                raise HTTPException(429, "Demasiados intentos. Intenta más tarde.", headers={"Retry-After": "900"})


def _session_response(user, session_id, refresh_token, response, mfa_verified=False):
    now = datetime.now(UTC)
    claims = {
        "sub": str(user["id"]), "sid": str(session_id), "jti": str(uuid4()),
        "iss": settings.jwt_issuer, "aud": "authenticated",
        "iat": now, "nbf": now, "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {
        "access_token": token, "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60, "refresh_token": refresh_token,
        "mfa_required": _requires_mfa(user) and not mfa_verified,
        "user": {"id": str(user["id"]), "email": user["email"], "app_metadata": {"role": user["role"], "auth_provider": "aquabloom"}},
    }


def _requires_mfa(user):
    return settings.environment == "production" and user["role"] == "administrador"


def _new_session(user, response, mfa_verified=False):
    session_id, token = str(uuid4()), secrets.token_urlsafe(48)
    duration = timedelta(hours=8) if _requires_mfa(user) else timedelta(days=settings.refresh_token_days)
    if _requires_mfa(user) and not mfa_verified:
        duration = timedelta(minutes=5)
    with require_database().connection() as connection:
        connection.execute(
            """INSERT INTO public.auth_sessions(id,user_id,refresh_hash,expires_at,mfa_verified)
               VALUES(%s,%s,%s,%s,%s)""",
            (session_id, str(user["id"]), digest(token), datetime.now(UTC) + duration, mfa_verified),
        )
        connection.execute("DELETE FROM public.auth_sessions WHERE expires_at < now()")
        connection.execute("DELETE FROM public.login_attempts WHERE window_start < now()-interval '1 day'")
    return _session_response(user, session_id, token, response, mfa_verified)


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response):
    if not settings.allow_registration:
        raise HTTPException(403, "El registro público está deshabilitado.")
    _rate_limit(request, payload.email)
    try:
        user = create_user(payload.email, payload.password.get_secret_value(), payload.full_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        if getattr(exc, "sqlstate", None) == "23505":
            raise HTTPException(409, "No se pudo registrar la cuenta.") from exc
        raise
    return _new_session(user, response)


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    _rate_limit(request, payload.email)
    with require_database().connection() as connection:
        user = connection.execute(
            "SELECT id,email,role,password_hash,status FROM public.users WHERE email=%s",
            (payload.email,),
        ).fetchone()
    # Always compute one scrypt hash, including for absent accounts.
    encoded = user["password_hash"] if user else DUMMY_PASSWORD_HASH
    matched = verify_password(payload.password.get_secret_value(), encoded)
    if not user or not matched or user["status"] != "active":
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    with require_database().connection() as connection:
        verified, _ = consume_second_factor(
            connection, user["id"], payload.second_factor.get_secret_value() if payload.second_factor else None,
        )
    return _new_session(user, response, verified)


@router.post("/refresh")
def refresh(payload: RefreshInput, request: Request, response: Response):
    _rate_limit(request, "refresh:" + digest(payload.refresh_token.get_secret_value()))
    token = secrets.token_urlsafe(48)
    with require_database().connection() as connection:
        row = connection.execute(
            """SELECT s.id,s.user_id,s.mfa_verified,u.email,u.role FROM public.auth_sessions s
               JOIN public.users u ON u.id=s.user_id
               WHERE s.refresh_hash=%s AND s.expires_at>now() AND u.status='active'
               AND (u.role<>'administrador' OR
                    (s.created_at>now()-interval '8 hours' AND s.last_activity_at>now()-interval '20 minutes'))
               FOR UPDATE OF s""", (digest(payload.refresh_token.get_secret_value()),),
        ).fetchone()
        if not row:
            raise HTTPException(401, "Sesión vencida o revocada.")
        connection.execute("UPDATE public.auth_sessions SET refresh_hash=%s WHERE id=%s", (digest(token), row["id"]))
    user = {"id": row["user_id"], "email": row["email"], "role": row["role"]}
    return _session_response(user, row["id"], token, response, row["mfa_verified"])


def verify_session(credentials, request, allow_enrollment=False):
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"], audience="authenticated", issuer=settings.jwt_issuer,
            options={"require": ["sub", "sid", "exp", "iat", "iss", "aud"]}, leeway=5,
        )
        user_id, session_id = str(UUID(payload["sub"])), str(UUID(payload["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise AuthException("Token inválido o vencido.", {"code": "INVALID_TOKEN"}) from exc
    with require_database().connection() as connection:
        user = connection.execute(
            """SELECT u.id,u.email,u.role,s.mfa_verified,s.created_at FROM public.users u
               JOIN public.auth_sessions s ON s.user_id=u.id
               WHERE u.id=%s AND s.id=%s AND u.status='active' AND s.expires_at>now()
               AND (u.role<>'administrador' OR
                    (s.created_at>now()-interval '8 hours' AND s.last_activity_at>now()-interval '20 minutes'))""",
            (user_id, session_id),
        ).fetchone()
        if user:
            if _requires_mfa(user) and not user["mfa_verified"] and not allow_enrollment:
                raise HTTPException(403, "Vincula y confirma tu segundo factor antes de acceder.")
            if _requires_mfa(user) and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                if user["created_at"] < datetime.now(UTC) - timedelta(minutes=5):
                    raise HTTPException(401, "Inicia sesión de nuevo para realizar esta operación.")
            # Polling and refresh never prolong the administrative inactivity window.
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                connection.execute("UPDATE public.auth_sessions SET last_activity_at=now() WHERE id=%s", (session_id,))
    if not user:
        raise AuthException("Sesión vencida o revocada.", {"code": "SESSION_REVOKED"})
    payload.update(email=user["email"], role=user["role"], app_metadata={"role": user["role"]})
    return payload


def verify_access_token(request: Request, credentials: HTTPAuthorizationCredentials = Security(security)):
    return verify_session(credentials, request)


def verify_enrollment_session(request: Request, credentials: HTTPAuthorizationCredentials = Security(security)):
    return verify_session(credentials, request, allow_enrollment=True)


def optional_verify_access_token(request: Request, credentials: HTTPAuthorizationCredentials | None = Security(optional_security)):
    return None if credentials is None else verify_access_token(request, credentials)


@router.post("/logout", status_code=204)
def logout(payload: dict = Security(verify_enrollment_session)):
    with require_database().connection() as connection:
        connection.execute("DELETE FROM public.auth_sessions WHERE id=%s AND user_id=%s", (payload["sid"], payload["sub"]))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(payload: dict = Security(verify_access_token)):
    from app.services import get_current_user_profile
    return get_current_user_profile(require_database(), UUID(payload["sub"]), payload["email"])


def require_admin(payload: dict = Security(verify_access_token)):
    if not has_permission(payload, "admin"):
        raise HTTPException(403, "Solo los administradores pueden realizar esta acción.")
    return payload


def _catalog_permission(payload, action):
    if not has_permission(payload, action):
        raise HTTPException(403, "No tienes permisos para esta acción del catálogo.")
    return payload


def require_catalog_create_permission(payload: dict = Security(verify_access_token)):
    return _catalog_permission(payload, CATALOG_ACTIONS["CREATE"])


def require_catalog_update_permission(payload: dict = Security(verify_access_token)):
    return _catalog_permission(payload, CATALOG_ACTIONS["UPDATE"])


def require_catalog_disable_permission(payload: dict = Security(verify_access_token)):
    return _catalog_permission(payload, CATALOG_ACTIONS["DISABLE"])
