"""Salted scrypt password hashing; never persist or log plaintext passwords."""
import base64
import hashlib
import hmac
import secrets
import threading

_HASH_LOCK = threading.BoundedSemaphore(1)
N, R, P = 131072, 8, 1


def validate_password(password: str):
    if not 12 <= len(password) <= 256 or any(ord(char) < 32 for char in password):
        raise ValueError("La contraseña debe contener entre 12 y 256 caracteres sin controles.")


def hash_password(password: str, salt: bytes | None = None):
    salt = salt or secrets.token_bytes(16)
    with _HASH_LOCK:
        value = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, maxmem=256*1024*1024)
    return "scrypt-v1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(value).decode()


def verify_password(password: str, encoded: str):
    try:
        version, salt, expected = encoded.split("$")
        if version != "scrypt-v1":
            return False
        actual = hash_password(password, base64.b64decode(salt, validate=True)).split("$")[2]
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False
