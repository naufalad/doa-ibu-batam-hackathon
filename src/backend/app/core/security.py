"""Password hashing and JWT issuance/verification.

Password hashing mirrors what `users.py` did inline before roles existed
(pbkdf2-hmac-sha256, 600k iterations, random 16-byte salt) — just factored
out so both signup and login can share it.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> tuple[bytes, bytes]:
    """Return (password_hash, password_salt) for a freshly chosen password."""
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return password_hash, salt


def verify_password(password: str, password_hash: bytes, password_salt: bytes) -> bool:
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), password_salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate, password_hash)


def create_access_token(*, user_id: int, email: str, role: str, region_ids: list[int]) -> str:
    """Issue a JWT carrying the caller's id, role, and region assignments.

    Region assignments are baked into the token rather than looked up from
    the DB on every request, which keeps `get_current_user` a single decode
    with no DB round-trip. The tradeoff: reassigning a waste_bank admin to
    different regions only takes effect the next time they log in.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "region_ids": region_ids,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode + verify a JWT. Raises jwt.PyJWTError on any invalid/expired token."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
