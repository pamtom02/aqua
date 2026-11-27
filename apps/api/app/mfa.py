"""Owner-operated MFA enrollment; secrets are returned only over authenticated HTTPS."""
import secrets
from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import APIRouter, HTTPException, Request, Response, Security
from pydantic import BaseModel, ConfigDict, SecretStr

from app.auth import _new_session, _rate_limit, require_database, verify_enrollment_session
from app.second_factor import cipher, decrypt_secret, matching_counter, recovery_digest

router = APIRouter(prefix="/auth/mfa", tags=["Auth"])


class ConfirmationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: SecretStr


def recent_user(connection, payload):
    user = connection.execute(
        """SELECT u.id,u.email,u.role FROM public.users u
           JOIN public.auth_sessions s ON s.user_id=u.id
           WHERE u.id=%s AND s.id=%s AND s.created_at>now()-interval '5 minutes'
           FOR UPDATE OF u""", (payload["sub"], payload["sid"]),
    ).fetchone()
    if not user:
        raise HTTPException(401, "Inicia sesión de nuevo para configurar MFA.")
    return user


@router.post("/enroll")
def enroll(request: Request, response: Response, payload: dict = Security(verify_enrollment_session)):
    _rate_limit(request, "mfa:" + payload["sub"])
    secret = pyotp.random_base32()
    encrypted = cipher().encrypt(secret.encode("ascii")).decode("ascii")
    with require_database().connection() as connection:
        user = recent_user(connection, payload)
        credential = connection.execute(
            "SELECT enabled FROM public.user_mfa WHERE user_id=%s", (user["id"],),
        ).fetchone()
        if credential and credential["enabled"]:
            raise HTTPException(409, "El segundo factor ya está activado.")
        connection.execute(
            """INSERT INTO public.user_mfa(user_id,encrypted_secret) VALUES(%s,%s)
               ON CONFLICT(user_id) DO UPDATE SET encrypted_secret=EXCLUDED.encrypted_secret,
               last_counter=-1,created_at=now()""", (user["id"], encrypted),
        )
    response.headers["Cache-Control"] = "no-store"
    return {"provisioning_uri": pyotp.TOTP(secret).provisioning_uri(user["email"], issuer_name="AquaBloom"),
            "expires_in": 600, "enabled": False}


@router.post("/confirm")
def confirm(body: ConfirmationInput, request: Request, response: Response,
            payload: dict = Security(verify_enrollment_session)):
    _rate_limit(request, "mfa:" + payload["sub"])
    with require_database().connection() as connection:
        user = recent_user(connection, payload)
        credential = connection.execute(
            "SELECT * FROM public.user_mfa WHERE user_id=%s FOR UPDATE", (user["id"],),
        ).fetchone()
        if not credential or credential["enabled"]:
            raise HTTPException(409, "No hay una vinculación pendiente.")
        if credential["created_at"] < datetime.now(UTC) - timedelta(minutes=10):
            raise HTTPException(401, "La vinculación venció. Iníciala de nuevo.")
        counter = matching_counter(decrypt_secret(credential["encrypted_secret"]),
                                   body.code.get_secret_value(), credential["last_counter"])
        if counter is None:
            raise HTTPException(401, "Código de segundo factor inválido.")
        connection.execute(
            "UPDATE public.user_mfa SET enabled=true,last_counter=%s WHERE user_id=%s",
            (counter, user["id"]),
        )
        codes = [secrets.token_urlsafe(24) for _ in range(10)]
        for code in codes:
            connection.execute(
                "INSERT INTO public.mfa_recovery_codes(user_id,code_hash) VALUES(%s,%s)",
                (user["id"], recovery_digest(code)),
            )
        connection.execute("DELETE FROM public.auth_sessions WHERE user_id=%s", (user["id"],))
    result = _new_session(user, response, mfa_verified=True)
    result["recovery_codes"] = codes
    return result
