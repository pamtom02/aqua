"""Encrypted TOTP credentials and atomic consumption of second factors."""
import hashlib
import secrets
from datetime import UTC, datetime

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.config import settings


def cipher() -> Fernet:
    configured = settings.mfa_encryption_key
    try:
        if configured is None:
            raise ValueError("Missing key")
        return Fernet(configured.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeError):
        raise HTTPException(503, "Cifrado de MFA sin configurar.") from None


def decrypt_secret(encrypted: str) -> str:
    try:
        return cipher().decrypt(encrypted.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeError):
        raise HTTPException(503, "No se pudo acceder al segundo factor.") from None


def matching_counter(secret: str, code: str, last_counter: int) -> int | None:
    """Permit one interval of clock drift, never an already consumed interval."""
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    now = datetime.now(UTC)
    for drift in (0, -1, 1):
        counter = totp.timecode(now) + drift
        if counter > last_counter and secrets.compare_digest(totp.at(counter * totp.interval), code):
            return counter
    return None


def recovery_digest(code: str) -> str:
    # These codes have 192 random bits; a fast cryptographic hash is appropriate.
    return hashlib.sha256(code.encode()).hexdigest()


def consume_second_factor(connection, user_id, code: str | None) -> tuple[bool, bool]:
    """The row lock serializes replay protection across all server processes."""
    credential = connection.execute(
        "SELECT * FROM public.user_mfa WHERE user_id=%s FOR UPDATE", (user_id,),
    ).fetchone()
    if not credential or not credential["enabled"]:
        return False, False
    if code is None:
        raise HTTPException(401, "Se requiere el segundo factor.")
    counter = matching_counter(
        decrypt_secret(credential["encrypted_secret"]), code, credential["last_counter"],
    )
    if counter is not None:
        connection.execute(
            "UPDATE public.user_mfa SET last_counter=%s WHERE user_id=%s", (counter, user_id),
        )
        return True, False
    recovered = connection.execute(
        "DELETE FROM public.mfa_recovery_codes WHERE user_id=%s AND code_hash=%s RETURNING user_id",
        (user_id, recovery_digest(code)),
    ).fetchone()
    if recovered:
        connection.execute("DELETE FROM public.auth_sessions WHERE user_id=%s", (user_id,))
        return True, True
    raise HTTPException(401, "Segundo factor inválido o ya utilizado.")
