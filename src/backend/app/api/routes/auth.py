"""Login endpoint — exchanges email+password for a JWT.

Uses the standard OAuth2 password-grant form shape (`username`, `password`,
plus the `grant_type`/`scope`/`client_id`/`client_secret` fields the spec
allows) via `OAuth2PasswordRequestForm`, since that's what Swagger UI's
"Authorize" dialog POSTs to the `tokenUrl` configured on `OAuth2PasswordBearer`
in app/api/deps.py. `username` is treated as the account's email.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import create_access_token, verify_password
from app.db import get_engine, users, waste_bank_regions
from app.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["auth"])

_email_adapter = TypeAdapter(EmailStr)


@router.post("/login", response_model=Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    password = form_data.password
    try:
        email = _email_adapter.validate_python(form_data.username)
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email address")

    with get_engine().connect() as conn:
        row = conn.execute(
            select(users.c.id, users.c.email, users.c.password_hash, users.c.password_salt, users.c.role).where(
                users.c.email == email
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        user_id, email, password_hash, password_salt, role = row
        if not verify_password(password, password_hash, password_salt):
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
