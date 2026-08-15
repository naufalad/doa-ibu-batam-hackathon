"""Pydantic schemas for users / points balance."""

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    points_balance: int = 0

    model_config = {"from_attributes": True}
