"""
Security utilities: password hashing and JWT issuance/verification.

AIB v1.0 Vol 6.2/6.3 — JWT-based auth, bcrypt password hashing.
AIB v1.0 Vol 6.7 — passwords never stored in plaintext; JWT secret
loaded from environment (never hardcoded).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

settings = get_settings()


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: uuid.UUID | str, expires_minutes: int | None = None) -> str:
    expire_minutes = expires_minutes or settings.jwt_expire_minutes
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire_at, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or invalid."""


def decode_access_token(token: str) -> uuid.UUID:
    """Returns the user id encoded in a valid token, else raises TokenError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    subject = payload.get("sub")
    if subject is None:
        raise TokenError("Token missing subject claim")

    try:
        return uuid.UUID(subject)
    except (ValueError, TypeError) as exc:
        raise TokenError("Token subject is not a valid user id") from exc
