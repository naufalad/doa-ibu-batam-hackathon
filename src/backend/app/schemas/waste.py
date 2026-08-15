"""Pydantic schemas for waste-sorting submissions."""

from datetime import datetime

from pydantic import BaseModel


class WasteObjectPrediction(BaseModel):
    """One detected+classified object within a submitted photo, plus the
    point-range token it earned (see app/services/rewards_policy.py)."""

    index: int
    coco_label: str
    segmentation_score: float
    bbox_xyxy: tuple[int, int, int, int]
    waste_label: str
    waste_confidence: float
    weight_kg: float | None = None

    token_id: int
    start_range: int
    end_range: int
    used: bool = False


class WasteSubmissionOut(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    num_objects: int
    objects: list[WasteObjectPrediction]
    status: str  # "pending_pickup" | "collected"
    segmented_image_path: str | None = None
    results_grid_path: str | None = None

    model_config = {"from_attributes": True}


class TokenDrawOut(BaseModel):
    """Result of drawing a waste token's point range."""

    token_id: int
    points_awarded: int
    points_balance: int


class PendingPickupOut(BaseModel):
    """A waste_bank/authorized-facing view of one submission awaiting
    pickup, with enough of the submitter's info to go collect it."""

    submission_id: int
    status: str
    created_at: datetime
    num_objects: int
    user_id: int
    user_name: str
    user_address: str | None = None
    region_id: int | None = None
    region_name: str | None = None

    model_config = {"from_attributes": True}
