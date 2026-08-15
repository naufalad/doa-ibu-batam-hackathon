"""Rewards catalog + redemption endpoints. Skeleton only."""

from fastapi import APIRouter, HTTPException, status

from src.backend.app.schemas.reward import RedemptionCreate, RedemptionOut, RewardOut

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=list[RewardOut])
def list_rewards() -> list[RewardOut]:
    # TODO: fetch from database.
    return []


@router.post("/redeem", response_model=RedemptionOut, status_code=status.HTTP_201_CREATED)
def redeem_reward(payload: RedemptionCreate) -> RedemptionOut:
    # TODO: verify user has enough points, decrement balance, create redemption.
    raise HTTPException(status_code=501, detail="Not implemented yet")
