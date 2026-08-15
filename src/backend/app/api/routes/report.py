"""LLM-generated activity report endpoint.

Pulls a user's historical waste-sorting transactions and asks the
configured LLM provider (see `app/services/llm/`, switchable via the
`LLM_PROVIDER` env var: openai/claude/ollama) to summarize their habits.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.schemas.report import UserReportOut
from app.services.llm import LLMProviderError
from app.services.report_generator import generate_user_report
from app.services.transactions import get_user_transactions

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/me", response_model=UserReportOut)
async def get_my_report(
    days: int = 30,
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> UserReportOut:
    """Caller's own report — no user_id to pass in, the id comes from the JWT."""
    return await _build_report(current_user.id, days, settings)


@router.get("/{user_id}", response_model=UserReportOut)
async def get_user_report(
    user_id: int,
    days: int = 30,
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> UserReportOut:
    """Self or `authorized` only, mirroring `GET /users/{user_id}`. Prefer
    `GET /report/me` when the caller is requesting their own report."""
    if current_user.role != "authorized" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's report")
    return await _build_report(user_id, days, settings)


async def _build_report(user_id: int, days: int, settings: Settings) -> UserReportOut:
    transactions = get_user_transactions(user_id, days=days)
    if not transactions:
        raise HTTPException(status_code=404, detail="No transaction history for this user in the given period")

    try:
        return await generate_user_report(user_id, transactions, settings, period_days=days)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
