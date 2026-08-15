"""Rewards catalog + redemption endpoints. Skeleton only."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select, update

from app.api.deps import CurrentUser, require_roles
from app.db import get_engine, redemptions, rewards as rewards_table, users
from app.schemas.reward import RedemptionCreate, RedemptionOut, RewardOut

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=list[RewardOut])
def list_rewards() -> list[RewardOut]:
    return []


@router.post("/redeem", response_model=RedemptionOut, status_code=status.HTTP_201_CREATED)
def redeem_reward(
    payload: RedemptionCreate,
    current_user: CurrentUser = Depends(require_roles("user")),
) -> RedemptionOut:
    with get_engine().begin() as conn:
        reward = conn.execute(
            select(rewards_table.c.cost_points, rewards_table.c.stock).where(
                rewards_table.c.id == payload.reward_id
            )
        ).first()
        if reward is None:
            raise HTTPException(status_code=404, detail="Reward not found")
        cost_points, stock = reward
        if stock <= 0:
            raise HTTPException(status_code=409, detail="Reward is out of stock")

        result = conn.execute(
            update(users)
            .where(users.c.id == current_user.id, users.c.points_balance >= cost_points)
            .values(points_balance=users.c.points_balance - cost_points)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Insufficient points")

        conn.execute(
            update(rewards_table)
            .where(rewards_table.c.id == payload.reward_id)
            .values(stock=rewards_table.c.stock - 1)
        )
        row = conn.execute(
            insert(redemptions)
            .values(reward_id=payload.reward_id, user_id=current_user.id, status="pending")
            .returning(redemptions.c.id, redemptions.c.reward_id, redemptions.c.user_id, redemptions.c.status)
        ).first()

    return RedemptionOut(id=row[0], reward_id=row[1], user_id=row[2], status=row[3])
