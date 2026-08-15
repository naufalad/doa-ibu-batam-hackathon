"""Pickup-schedule policy for the "picked up" delivery flow.

TODO: this is a placeholder, same spirit as the placeholder in
`rewards_policy.py` — replace with a real slot-booking system (per-region
collection routes/days, capacity limits, a user-picked time window) once
that's defined. For now it just returns the next daily collection round's
start time, so `POST /waste/submissions/{id}/delivery-method` has a
concrete slot to hand back to a user who chooses "pickup".
"""

from datetime import datetime, time, timedelta, timezone

# waste_bank collectors are assumed to run one round a day, arriving
# sometime after this hour (UTC).
_COLLECTION_WINDOW_START = time(hour=9, tzinfo=timezone.utc)


def compute_next_pickup_slot(now: datetime) -> datetime:
    """Next day's collection-round start, in UTC.

    Always rolls to tomorrow, even for an early-morning request — there's
    only one round a day, so there's no same-day cutoff to check against.
    """
    next_day = (now.astimezone(timezone.utc) + timedelta(days=1)).date()
    return datetime.combine(next_day, _COLLECTION_WINDOW_START)
