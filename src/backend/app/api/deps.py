"""Auth dependencies: decode the caller's JWT into a `CurrentUser`, and
gate routes by role.

`region_ids` comes straight from the token (see
`app/core/security.py::create_access_token`), not a fresh DB lookup —
cheap, but means a waste_bank admin's region reassignment only takes
effect on their next login.
"""

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class CurrentUser:
    id: int
    email: str
    role: str
    region_ids: list[int]


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    user_id = payload.get("sub")
    role = payload.get("role")
    if user_id is None or role is None:
        raise credentials_error

    return CurrentUser(
        id=int(user_id),
        email=payload.get("email", ""),
        role=role,
        region_ids=payload.get("region_ids") or [],
    )


def require_roles(*roles: str):
    """Dependency factory: 403s unless the caller's role is one of `roles`."""

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this action")
        return current_user

    return _check
