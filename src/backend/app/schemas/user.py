"""Pydantic schemas for users / points balance / roles."""

from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class RoleEnum(str, Enum):
    user = "user"
    waste_bank = "waste_bank"
    authorized = "authorized"


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    """Public self-signup. Always creates role=`user` — the other two
    roles are provisioned by an `authorized` account (see
    `WasteBankAdminCreate` and the create_admin bootstrap script)."""

    password: str
    address: str | None = None
    region_id: int | None = None


class UserOut(UserBase):
    id: int
    role: RoleEnum
    points_balance: int = 0
    address: str | None = None
    region_id: int | None = None

    model_config = {"from_attributes": True}


class WasteBankAdminCreate(UserBase):
    """`authorized`-only: provisions a waste_bank admin scoped to one or
    more regions."""

    password: str
    region_ids: list[int] = Field(min_length=1)


class WasteBankAdminOut(UserBase):
    id: int
    role: RoleEnum
    region_ids: list[int]

    model_config = {"from_attributes": True}
