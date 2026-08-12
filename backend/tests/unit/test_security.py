"""Unit tests for security utilities — AIB v1.0 Vol 6.12, Vol 15.4."""

import uuid

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext():
    hashed = hash_password("MySecret123")
    assert hashed != "MySecret123"
    assert hashed.startswith("$2b$")  # bcrypt marker


def test_password_verify_correct_and_incorrect():
    hashed = hash_password("MySecret123")
    assert verify_password("MySecret123", hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    decoded = decode_access_token(token)
    assert decoded == user_id


def test_jwt_rejects_garbage_token():
    with pytest.raises(TokenError):
        decode_access_token("not-a-real-token")


def test_jwt_expired_token_is_rejected():
    user_id = uuid.uuid4()
    # Negative expiry -> token is already expired the instant it's issued.
    token = create_access_token(user_id, expires_minutes=-1)
    with pytest.raises(TokenError):
        decode_access_token(token)
