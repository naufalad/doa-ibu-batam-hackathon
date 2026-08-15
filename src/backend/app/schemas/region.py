"""Pydantic schemas for regions."""

from pydantic import BaseModel


class RegionCreate(BaseModel):
    name: str


class RegionOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
