"""Pydantic schemas for rewards / redemptions."""

from pydantic import BaseModel


class RewardOut(BaseModel):
    id: int
    title: str
    description: str
    cost_points: int
    stock: int

    model_config = {"from_attributes": True}


class RedemptionCreate(BaseModel):
    reward_id: int


class RedemptionOut(BaseModel):
    id: int
    reward_id: int
    user_id: int
    status: str  # "pending" | "fulfilled" | "cancelled"

    model_config = {"from_attributes": True}
