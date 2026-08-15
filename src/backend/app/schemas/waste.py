"""Pydantic schemas for waste-sorting submissions."""

from datetime import datetime
from typing import Literal

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
    # "pending_choice" | "pending_pickup" | "pending_dropoff" | "collected" | "dropped_off"
    status: str
    delivery_method: Literal["pickup", "self_dropoff"] | None = None
    scheduled_pickup_at: datetime | None = None
    dropoff_waste_bank_id: int | None = None
    segmented_image_path: str | None = None
    results_grid_path: str | None = None

    model_config = {"from_attributes": True}


class TokenDrawOut(BaseModel):
    """Result of drawing a waste token's point range."""

    token_id: int
    points_awarded: int
    points_balance: int


class DeliveryMethodChoice(BaseModel):
    """Body for POST /waste/submissions/{id}/delivery-method."""

    method: Literal["pickup", "self_dropoff"]


class NearestWasteBankOut(BaseModel):
    """The waste_bank admin a self-dropoff submitter was pointed to.

    "Nearest" is currently just "covers the submitter's region" — there's
    no lat/lng on waste_bank accounts yet to do real distance ranking.
    """

    id: int
    name: str
    address: str | None = None
    region_id: int | None = None
    region_name: str | None = None

    model_config = {"from_attributes": True}


class DeliveryChoiceOut(BaseModel):
    """Result of choosing a delivery method: a pickup slot, or the
    nearest waste_bank to drop off at — whichever applies."""

    submission_id: int
    status: str
    delivery_method: Literal["pickup", "self_dropoff"]
    scheduled_pickup_at: datetime | None = None
    waste_bank: NearestWasteBankOut | None = None


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


class WasteRecordOut(BaseModel):
    """A single submission row in the all-statuses waste listing — every
    status the submission can be in (`pending_choice`, `pending_pickup`,
    `pending_dropoff`, `collected`, `dropped_off`), not just what's still
    outstanding. Visibility is scoped by caller role (see GET
    /waste/history)."""

    submission_id: int
    status: str
    delivery_method: Literal["pickup", "self_dropoff"] | None = None
    created_at: datetime
    collected_at: datetime | None = None
    num_objects: int
    user_id: int
    user_name: str
    user_address: str | None = None
    region_id: int | None = None
    region_name: str | None = None

    model_config = {"from_attributes": True}
