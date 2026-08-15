"""Builds the LLM prompt from a user's transaction history and turns the
reply into a `UserReportOut`. The LLM only ever writes the free-text
`narrative` — every numeric field is computed locally so the report can't
misreport a user's own points/category totals.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from src.backend.app.core.config import Settings
from src.backend.app.schemas.report import TransactionSummary, UserReportOut
from src.backend.app.services.llm import get_llm_provider

SYSTEM_PROMPT = (
    "You are a friendly waste-sorting coach for Pilahin, an app that rewards "
    "users with points for sorting their waste properly. Given a user's "
    "recent sorting activity, write a short, encouraging report."
)


async def generate_user_report(
    user_id: int,
    transactions: list[TransactionSummary],
    settings: Settings,
    period_days: int = 30,
) -> UserReportOut:
    total_submissions = len(transactions)
    total_points = sum(t.points_awarded for t in transactions)
    category_counts = Counter(t.waste_label for t in transactions)
    top_categories = [label for label, _count in category_counts.most_common(3)]

    provider = get_llm_provider(settings)
    narrative = await provider.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(user_id, transactions, total_points, top_categories, period_days)},
        ],
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )

    return UserReportOut(
        user_id=user_id,
        generated_at=datetime.now(timezone.utc),
        period_days=period_days,
        total_submissions=total_submissions,
        total_points=total_points,
        top_categories=top_categories,
        narrative=narrative.strip(),
        llm_provider=settings.llm_provider,
    )


def _build_prompt(
    user_id: int,
    transactions: list[TransactionSummary],
    total_points: int,
    top_categories: list[str],
    period_days: int,
) -> str:
    lines = [
        f"- {t.date:%Y-%m-%d}: {t.num_objects} item(s) sorted as '{t.waste_label}' (+{t.points_awarded} pts)"
        for t in transactions
    ]
    return (
        f"User #{user_id}'s waste-sorting activity over the last {period_days} days:\n\n"
        + "\n".join(lines)
        + f"\n\nTotals: {total_points} points earned across {len(transactions)} submissions. "
        f"Top categories: {', '.join(top_categories) if top_categories else 'none'}.\n\n"
        "Write 2-3 sentences summarizing their sorting habits and one concrete tip "
        "to help them earn more points or diversify what they sort."
    )
