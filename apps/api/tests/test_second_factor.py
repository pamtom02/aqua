from datetime import UTC, datetime

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr

from app.config import settings
from app.second_factor import cipher, decrypt_secret, matching_counter


def test_encryption_requires_separate_valid_key_and_detects_tampering(monkeypatch):
    monkeypatch.setattr(settings, "mfa_encryption_key", None)
    with pytest.raises(HTTPException):
        cipher()
    monkeypatch.setattr(settings, "mfa_encryption_key", SecretStr(Fernet.generate_key().decode()))
    secret = pyotp.random_base32()
    encrypted = cipher().encrypt(secret.encode()).decode()
    assert secret not in encrypted
    assert decrypt_secret(encrypted) == secret
    with pytest.raises(HTTPException):
        decrypt_secret(encrypted[:-4] + "AAAA")


def test_totp_drift_and_replay_protection():
    totp = pyotp.TOTP(pyotp.random_base32())
    now = datetime.now(UTC)
    counter = totp.timecode(now)
    code = totp.at(counter * 30)
    assert matching_counter(totp.secret, code, counter - 1) == counter
    assert matching_counter(totp.secret, code, counter) is None
    assert matching_counter(totp.secret, "bad", -1) is None
