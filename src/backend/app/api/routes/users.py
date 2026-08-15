"""User endpoints: self-signup, waste_bank admin provisioning, profile lookup."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.security import hash_password
from app.db import get_engine, regions, users, waste_bank_regions
from app.schemas.user import (
    UserCreate,
    UserOut,
    WasteBankAdminCreate,
    WasteBankAdminOut,
)

router = APIRouter(prefix="/users", tags=["users"])

_USER_COLUMNS = (
    users.c.id,
    users.c.email,
    users.c.name,
    users.c.role,
    users.c.points_balance,
    users.c.address,
    users.c.region_id,
)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserOut:
    """Public self-signup. Always creates role='user' — see
    `POST /users/waste-bank-admins` for the other roles."""
    password_hash, password_salt = hash_password(payload.password)
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                insert(users)
                .values(
                    email=str(payload.email),
                    name=payload.name,
                    password_hash=password_hash,
                    password_salt=password_salt,
                    role="user",
                    address=payload.address,
                    region_id=payload.region_id,
                )
                .returning(*_USER_COLUMNS)
            ).first()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc

    return _user_out(row)


@router.post("/waste-bank-admins", response_model=WasteBankAdminOut, status_code=status.HTTP_201_CREATED)
def create_waste_bank_admin(
    payload: WasteBankAdminCreate,
    _current_user: CurrentUser = Depends(require_roles("authorized")),
) -> WasteBankAdminOut:
    """`authorized`-only: provisions a waste_bank admin scoped to one or more regions."""
    password_hash, password_salt = hash_password(payload.password)
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                insert(users)
                .values(
                    email=str(payload.email),
                    name=payload.name,
                    password_hash=password_hash,
                    password_salt=password_salt,
                    role="waste_bank",
                )
                .returning(users.c.id, users.c.email, users.c.name, users.c.role)
            ).first()
            user_id = row[0]

            found_region_ids = {
                r[0]
                for r in conn.execute(
                    select(regions.c.id).where(regions.c.id.in_(payload.region_ids))
                )
            }
            missing = set(payload.region_ids) - found_region_ids
            if missing:
                raise HTTPException(status_code=404, detail=f"Region(s) not found: {sorted(missing)}")

            conn.execute(
                insert(waste_bank_regions),
                [{"user_id": user_id, "region_id": region_id} for region_id in payload.region_ids],
            )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc

    return WasteBankAdminOut(id=row[0], email=row[1], name=row[2], role=row[3], region_ids=payload.region_ids)


@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return _fetch_user_or_404(current_user.id)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    """Self or `authorized` only. waste_bank admins never look up a user
    directly by id — they see submitter info through the region-scoped
    pickups list instead (see GET /waste/pickups)."""
    if current_user.role != "authorized" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user")
    return _fetch_user_or_404(user_id)


def _fetch_user_or_404(user_id: int) -> UserOut:
    with get_engine().connect() as conn:
        row = conn.execute(select(*_USER_COLUMNS).where(users.c.id == user_id)).first()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(row)


def _user_out(row) -> UserOut:
    return UserOut(
        id=row[0],
        email=row[1],
        name=row[2],
        role=row[3],
        points_balance=row[4],
        address=row[5],
        region_id=row[6],
    )
