"""Historical waste-submission lookups.

TODO: this is mock data so `/report` is exercisable before persistence
exists. Replace with a real query once `waste.py`'s submissions are
actually written to a database (see its TODO to persist `WasteSubmissionOut`
rows) — swap the body of `get_user_transactions` for a DB read keyed on
`user_id` and `since`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas.report import TransactionSummary

_MOCK_TRANSACTIONS = [
    TransactionSummary(date=datetime.now(timezone.utc) - timedelta(days=1), waste_label="plastic", num_objects=4, points_awarded=40),
    TransactionSummary(date=datetime.now(timezone.utc) - timedelta(days=3), waste_label="paper", num_objects=2, points_awarded=20),
    TransactionSummary(date=datetime.now(timezone.utc) - timedelta(days=6), waste_label="plastic", num_objects=3, points_awarded=30),
    TransactionSummary(date=datetime.now(timezone.utc) - timedelta(days=10), waste_label="glass", num_objects=1, points_awarded=10),
    TransactionSummary(date=datetime.now(timezone.utc) - timedelta(days=14), waste_label="battery", num_objects=1, points_awarded=10),
]


def get_user_transactions(user_id: int, days: int = 30) -> list[TransactionSummary]:
    """Return this user's waste submissions from the last `days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # TODO: filter by real user_id once submissions are persisted; every
    # user currently sees the same mock history.
    return [t for t in _MOCK_TRANSACTIONS if t.date >= cutoff]
