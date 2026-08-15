"""Login endpoint — exchanges email+password for a JWT."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.security import create_access_token, verify_password
from app.db import get_engine, users, waste_bank_regions
from app.schemas.auth import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest) -> Token:
    with get_engine().connect() as conn:
        row = conn.execute(
            select(users.c.id, users.c.email, users.c.password_hash, users.c.password_salt, users.c.role).where(
                users.c.email == str(payload.email)
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        user_id, email, password_hash, password_salt, role = row
        if not verify_password(payload.password, password_hash, password_salt):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        region_ids: list[int] = []
        if role == "waste_bank":
            region_ids = [
                r[0]
                for r in conn.execute(
                    select(waste_bank_regions.c.region_id).where(waste_bank_regions.c.user_id == user_id)
                )
            ]

    token = create_access_token(user_id=user_id, email=email, role=role, region_ids=region_ids)
    return Token(access_token=token)
