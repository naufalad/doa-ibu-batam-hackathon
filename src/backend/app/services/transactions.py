"""Historical waste-submission lookups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_engine, waste_submissions, waste_tokens, wastes
from app.schemas.report import TransactionSummary


def get_user_transactions(user_id: int, days: int = 30) -> list[TransactionSummary]:
    """Return this user's waste submissions from the last `days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    statement = (
        select(
            waste_submissions.c.created_at,
            func.coalesce(func.min(wastes.c.waste_label), "unknown"),
            func.count(wastes.c.id),
            func.coalesce(func.sum(waste_tokens.c.drawn_points), 0),
        )
        .select_from(
            waste_submissions.outerjoin(wastes, wastes.c.submission_id == waste_submissions.c.id).outerjoin(
                waste_tokens, waste_tokens.c.waste_id == wastes.c.id
            )
        )
        .where(waste_submissions.c.user_id == user_id, waste_submissions.c.created_at >= cutoff)
        .group_by(waste_submissions.c.id, waste_submissions.c.created_at)
        .order_by(waste_submissions.c.created_at.desc())
    )

    with get_engine().connect() as conn:
        rows = conn.execute(statement).all()

    return [
        TransactionSummary(date=date, waste_label=waste_label, num_objects=num_objects, points_awarded=points_awarded)
        for date, waste_label, num_objects, points_awarded in rows
    ]
