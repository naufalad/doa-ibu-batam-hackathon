"""Database engine + schema, via SQLAlchemy Core (no ORM).

Every table Pilahin needs is defined here as a `sqlalchemy.Table`, created
once at startup by `init_db()` (see the `lifespan` handler in
`src/backend/main.py`). Routes import the `Table` objects + `engine` from this
module and build `select`/`insert`/`update` expressions directly — there's
no session/ORM layer, just Core's expression language over a plain
`Engine`.
"""

from functools import lru_cache

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.engine import Engine

from src.backend.app.core.config import get_settings

metadata = MetaData()

regions = Table(
    "regions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, unique=True),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("password_hash", LargeBinary, nullable=False),
    Column("password_salt", LargeBinary, nullable=False),
    Column("role", String, nullable=False, server_default="user"),
    Column("address", String, nullable=True),
    Column("region_id", Integer, ForeignKey("regions.id"), nullable=True),
    Column("points_balance", Integer, nullable=False, server_default="0"),
    CheckConstraint("role IN ('user', 'waste_bank', 'authorized')", name="ck_users_role"),
)

# A waste_bank admin can cover multiple regions.
waste_bank_regions = Table(
    "waste_bank_regions",
    metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("region_id", Integer, ForeignKey("regions.id"), primary_key=True),
)

waste_submissions = Table(
    "waste_submissions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("segmented_image_path", String, nullable=True),
    Column("results_grid_path", String, nullable=True),
    Column("status", String, nullable=False, server_default="pending_pickup"),
    Column("collected_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("collected_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status IN ('pending_pickup', 'collected')", name="ck_waste_submissions_status"),
)

# One row per object detected in a submission's photo — a real entity
# (category, bbox, confidence, weight), not a JSON blob on the
# submission, since each one earns its own point-range token.
wastes = Table(
    "wastes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("submission_id", Integer, ForeignKey("waste_submissions.id"), nullable=False),
    Column("obj_index", Integer, nullable=False),
    Column("coco_label", String, nullable=False),
    Column("segmentation_score", Float, nullable=False),
    Column("bbox_x1", Integer, nullable=False),
    Column("bbox_y1", Integer, nullable=False),
    Column("bbox_x2", Integer, nullable=False),
    Column("bbox_y2", Integer, nullable=False),
    Column("waste_label", String, nullable=False),
    Column("waste_confidence", Float, nullable=False),
    Column("weight_kg", Float, nullable=True),
)

# A point-range "lottery ticket" per waste item. Points are only credited
# once the user draws the token (see POST /waste/tokens/{id}/draw) — see
# app/services/rewards_policy.py for how [start_range, end_range] is
# derived from category + weight.
waste_tokens = Table(
    "waste_tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("waste_id", Integer, ForeignKey("wastes.id"), nullable=False, unique=True),
    Column("start_range", Integer, nullable=False),
    Column("end_range", Integer, nullable=False),
    Column("used", Boolean, nullable=False, server_default="false"),
    Column("drawn_points", Integer, nullable=True),
    Column("drawn_at", DateTime(timezone=True), nullable=True),
)

rewards = Table(
    "rewards",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String, nullable=False),
    Column("description", String, nullable=False),
    Column("cost_points", Integer, nullable=False),
    Column("stock", Integer, nullable=False, server_default="0"),
)

redemptions = Table(
    "redemptions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reward_id", Integer, ForeignKey("rewards.id"), nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("status", String, nullable=False, server_default="pending"),
)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def init_db() -> None:
    """Create all tables if they don't already exist. Safe to call repeatedly."""
    metadata.create_all(get_engine())
