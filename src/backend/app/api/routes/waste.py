"""Waste-sorting submission endpoints.

A user uploads a photo of their sorted waste; the image is run through the
segmentation + classification pipeline (see `app/services/waste_classifier.py`
-> `pipeline/segment_classify.py`), and points are awarded based on what was
detected.
"""

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from src.backend.app.core.config import Settings, get_settings
from src.backend.app.schemas.waste import WasteObjectPrediction, WasteSubmissionOut
from src.backend.app.services.waste_classifier import WasteClassifierService

router = APIRouter(prefix="/waste", tags=["waste"])

# TODO: replace with a real scoring policy (e.g. points per waste category,
# bonus for correctly separated materials, etc.) once product rules land.
POINTS_PER_OBJECT = 10


@router.post("/submit", response_model=WasteSubmissionOut)
async def submit_waste_photo(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
) -> WasteSubmissionOut:
    """Classify an uploaded waste photo and report the points it earns.

    Runs the Mask2Former segmentation model to find individual objects in
    the photo, then the ViT waste-classifier on each detected object.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "upload.jpg").suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        classifier = WasteClassifierService.get(device=settings.ml_device)
        try:
            report = classifier.classify_image(tmp_path.as_posix())
        except Exception as exc:  # noqa: BLE001 - surface model/inference failures as a 502
            raise HTTPException(status_code=502, detail=f"Waste classification failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    objects = [
        WasteObjectPrediction(
            index=obj["index"],
            coco_label=obj["coco_label"],
            segmentation_score=obj["segmentation_score"],
            bbox_xyxy=obj["bbox_xyxy"],
            waste_label=obj["waste_label"],
            waste_confidence=obj["waste_confidence"],
        )
        for obj in report["objects"]
    ]

    # TODO: persist the submission (real user from auth, DB-assigned id,
    # updated points balance) instead of fabricating id=0/user_id=0 here.
    return WasteSubmissionOut(
        id=0,
        user_id=0,
        created_at=datetime.now(timezone.utc),
        num_objects=report["num_objects"],
        objects=objects,
        points_awarded=POINTS_PER_OBJECT * report["num_objects"],
    )
