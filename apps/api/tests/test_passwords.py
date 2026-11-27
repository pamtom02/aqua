import pytest

from app.passwords import hash_password, validate_password, verify_password


@pytest.mark.parametrize("password", ["short", "a" * 100, "passwordpassword123!", "12345678901234567890", "x" * 257])
def test_rejects_short_common_and_oversized_new_passwords(password):
    with pytest.raises(ValueError):
        validate_password(password)


def test_scrypt_salts_and_existing_short_password_compatibility():
    # New password rules must not lock out users with an existing valid hash.
    first = hash_password("old-password")
    second = hash_password("old-password")
    assert first != second
    assert verify_password("old-password", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("old-password", "malformed")
