"""Pydantic schemas for login / JWT issuance."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
