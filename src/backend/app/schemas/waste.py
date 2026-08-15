"""Pydantic schemas for waste-sorting submissions."""

from datetime import datetime

from pydantic import BaseModel


class WasteObjectPrediction(BaseModel):
    """One detected+classified object within a submitted photo."""

    index: int
    coco_label: str
    segmentation_score: float
    bbox_xyxy: tuple[int, int, int, int]
    waste_label: str
    waste_confidence: float


class WasteSubmissionOut(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    num_objects: int
    objects: list[WasteObjectPrediction]
    points_awarded: int

    model_config = {"from_attributes": True}
