"""JWT issue + verify utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from hospital.config import get_settings


def _settings():
    return get_settings()


def create_access_token(
    sub: str,
    email: str,
    name: str | None,
    role: str,
    *,
    expire_minutes: int | None = None,
) -> str:
    settings = _settings()
    minutes = expire_minutes or settings.JWT_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "name": name or "",
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    """Decode and verify a JWT.  Raises JWTError on failure."""
    settings = _settings()
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )


def is_token_expired(token: str) -> bool:
    try:
        decode_token(token)
        return False
    except JWTError:
        return True
