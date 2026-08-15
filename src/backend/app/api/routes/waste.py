"""Waste-sorting submission + pickup/dropoff endpoints.

A `user` uploads a photo of their sorted waste; the image is run through
the segmentation + classification pipeline (see
`app/services/waste_classifier.py` -> `pipeline/segment_classify.py`).
Each detected object becomes its own `wastes` row plus a `waste_tokens`
point-range ticket (see `app/services/rewards_policy.py`) — points are
only credited once the user draws the token via `/waste/tokens/{id}/draw`.

Once submitted, a submission sits at status "pending_choice" until the
user picks how it gets to a waste_bank, via
`POST /waste/submissions/{id}/delivery-method`:

  - "pickup": status -> "pending_pickup", and the response includes the
    scheduled collection slot (`app/services/pickup_scheduler.py`).
    `waste_bank`/`authorized` accounts then use `/waste/pickups` to see
    submissions still awaiting collection (region-scoped for waste_bank)
    and `/waste/pickups/{id}/collect` to mark one collected.
  - "self_dropoff": status -> "pending_dropoff", and the response
    includes the nearest waste_bank to drop it off at. When the user
    actually shows up and drops it off, `POST
    /waste/dropoffs/{id}/confirm` is meant to be hit automatically by
    that waste_bank's intake system to mark it "dropped_off".
"""

import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import func, insert, select, update

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.db import get_engine, regions, users, waste_bank_regions, waste_submissions, waste_tokens, wastes
from app.schemas.waste import (
    DeliveryChoiceOut,
    DeliveryMethodChoice,
    NearestWasteBankOut,
    PendingPickupOut,
    TokenDrawOut,
    WasteObjectPrediction,
    WasteRecordOut,
    WasteSubmissionOut,
)
from app.services.pickup_scheduler import compute_next_pickup_slot
from app.services.rewards_policy import compute_token_range
from app.services.waste_classifier import WasteClassifierService

router = APIRouter(prefix="/waste", tags=["waste"])


@router.post("/submit", response_model=WasteSubmissionOut)
async def submit_waste_photo(
    file: UploadFile,
    weight_kg: float | None = Form(
        None, description="Total weight of this photo's waste, split evenly across detected objects."
    ),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(require_roles("user")),
) -> WasteSubmissionOut:
    """Classify an uploaded waste photo, persist it, and issue a point-range
    token per detected object.

    Runs the Mask2Former segmentation model to find individual objects in
    the photo, then the ViT waste-classifier on each detected object.
    The resulting submission starts at status "pending_choice" — see
    `POST /waste/submissions/{id}/delivery-method` for what comes next.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "upload.jpg").suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    submitted_at = datetime.now(timezone.utc)
    stem = f"{submitted_at:%Y%m%dT%H%M%S}_{uuid4().hex[:8]}"

    try:
        classifier = WasteClassifierService.get(device=settings.ml_device)
        try:
            report = classifier.classify_image(
                tmp_path.as_posix(),
                save_dir=settings.waste_output_dir,
                save_stem=stem,
            )
        except Exception as exc:  # noqa: BLE001 - surface model/inference failures as a 502
            raise HTTPException(status_code=502, detail=f"Waste classification failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    detected = report["objects"]
    per_item_weight = weight_kg / len(detected) if weight_kg and detected else None

    with get_engine().begin() as conn:
        submission_id = conn.execute(
            insert(waste_submissions)
            .values(
                user_id=current_user.id,
                created_at=submitted_at,
                segmented_image_path=report.get("segmented_image_path"),
                results_grid_path=report.get("results_grid_path"),
                status="pending_choice",
            )
            .returning(waste_submissions.c.id)
        ).scalar_one()

        objects_out = []
        for obj in detected:
            x1, y1, x2, y2 = obj["bbox_xyxy"]
            waste_id = conn.execute(
                insert(wastes)
                .values(
                    submission_id=submission_id,
                    obj_index=obj["index"],
                    coco_label=obj["coco_label"],
                    segmentation_score=obj["segmentation_score"],
                    bbox_x1=x1,
                    bbox_y1=y1,
                    bbox_x2=x2,
                    bbox_y2=y2,
                    waste_label=obj["waste_label"],
                    waste_confidence=obj["waste_confidence"],
                    weight_kg=per_item_weight,
                )
                .returning(wastes.c.id)
            ).scalar_one()

            start_range, end_range = compute_token_range(
                obj["waste_label"], per_item_weight, obj["waste_confidence"]
            )
            token_id = conn.execute(
                insert(waste_tokens)
                .values(waste_id=waste_id, start_range=start_range, end_range=end_range)
                .returning(waste_tokens.c.id)
            ).scalar_one()

            objects_out.append(
                WasteObjectPrediction(
                    index=obj["index"],
                    coco_label=obj["coco_label"],
                    segmentation_score=obj["segmentation_score"],
                    bbox_xyxy=(x1, y1, x2, y2),
                    waste_label=obj["waste_label"],
                    waste_confidence=obj["waste_confidence"],
                    weight_kg=per_item_weight,
                    token_id=token_id,
                    start_range=start_range,
                    end_range=end_range,
                    used=False,
                )
            )

    return WasteSubmissionOut(
        id=submission_id,
        user_id=current_user.id,
        created_at=submitted_at,
        num_objects=len(objects_out),
        objects=objects_out,
        status="pending_choice",
        segmented_image_path=report.get("segmented_image_path"),
        results_grid_path=report.get("results_grid_path"),
    )


@router.post("/submissions/{submission_id}/delivery-method", response_model=DeliveryChoiceOut)
def choose_delivery_method(
    submission_id: int,
    payload: DeliveryMethodChoice,
    current_user: CurrentUser = Depends(require_roles("user")),
) -> DeliveryChoiceOut:
    """Record how a submission's waste is getting to a waste_bank, and
    hand back what that means for the user: a pickup slot, or the
    nearest waste_bank to drop it off at themselves.

    One-shot per submission — the submission must still be at status
    "pending_choice" (i.e. this hasn't been called for it before).
    """
    with get_engine().begin() as conn:
        row = conn.execute(
            select(waste_submissions.c.user_id).where(waste_submissions.c.id == submission_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if row[0] != current_user.id:
            raise HTTPException(status_code=403, detail="This submission doesn't belong to you")

        if payload.method == "pickup":
            scheduled_at = compute_next_pickup_slot(datetime.now(timezone.utc))
            result = conn.execute(
                update(waste_submissions)
                .where(waste_submissions.c.id == submission_id, waste_submissions.c.status == "pending_choice")
                .values(delivery_method="pickup", status="pending_pickup", scheduled_pickup_at=scheduled_at)
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=409, detail="Delivery method already chosen for this submission")

            return DeliveryChoiceOut(
                submission_id=submission_id,
                status="pending_pickup",
                delivery_method="pickup",
                scheduled_pickup_at=scheduled_at,
            )

        # self_dropoff: point the user at the waste_bank admin covering
        # their region. There's no lat/lng on waste_bank accounts yet, so
        # "nearest" is really just "covers my region" — first match wins.
        user_region_id = conn.execute(
            select(users.c.region_id).where(users.c.id == current_user.id)
        ).scalar_one_or_none()

        waste_bank_row = None
        if user_region_id is not None:
            waste_bank_row = conn.execute(
                select(users.c.id, users.c.name, users.c.address, regions.c.id, regions.c.name)
                .select_from(
                    waste_bank_regions.join(users, users.c.id == waste_bank_regions.c.user_id).join(
                        regions, regions.c.id == waste_bank_regions.c.region_id
                    )
                )
                .where(waste_bank_regions.c.region_id == user_region_id)
                .order_by(users.c.id)
                .limit(1)
            ).first()

        if waste_bank_row is None:
            raise HTTPException(status_code=404, detail="No waste bank is currently assigned to your region")
        wb_id, wb_name, wb_address, wb_region_id, wb_region_name = waste_bank_row

        result = conn.execute(
            update(waste_submissions)
            .where(waste_submissions.c.id == submission_id, waste_submissions.c.status == "pending_choice")
            .values(delivery_method="self_dropoff", status="pending_dropoff", dropoff_waste_bank_id=wb_id)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Delivery method already chosen for this submission")

    return DeliveryChoiceOut(
        submission_id=submission_id,
        status="pending_dropoff",
        delivery_method="self_dropoff",
        waste_bank=NearestWasteBankOut(
            id=wb_id, name=wb_name, address=wb_address, region_id=wb_region_id, region_name=wb_region_name
        ),
    )


@router.post("/tokens/{token_id}/draw", response_model=TokenDrawOut)
def draw_token(token_id: int, current_user: CurrentUser = Depends(require_roles("user"))) -> TokenDrawOut:
    """Draw a random point value from a waste token's [start_range, end_range]
    and credit it to the caller's points_balance. One-shot per token."""
    with get_engine().begin() as conn:
        row = conn.execute(
            select(waste_tokens.c.start_range, waste_tokens.c.end_range, waste_submissions.c.user_id)
            .select_from(
                waste_tokens.join(wastes, wastes.c.id == waste_tokens.c.waste_id).join(
                    waste_submissions, waste_submissions.c.id == wastes.c.submission_id
                )
            )
            .where(waste_tokens.c.id == token_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Token not found")
        start_range, end_range, owner_id = row
        if owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="This token doesn't belong to you")

        points_awarded = random.randint(start_range, end_range)

        # Atomic guard against a concurrent draw of the same token: the
        # WHERE clause only matches (and updates) an unused token, so two
        # simultaneous requests can't both slip past a separate SELECT
        # check the way a plain check-then-update would allow.
        result = conn.execute(
            update(waste_tokens)
            .where(waste_tokens.c.id == token_id, waste_tokens.c.used.is_(False))
            .values(used=True, drawn_points=points_awarded, drawn_at=datetime.now(timezone.utc))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Token already drawn")

        new_balance = conn.execute(
            update(users)
            .where(users.c.id == current_user.id)
            .values(points_balance=users.c.points_balance + points_awarded)
            .returning(users.c.points_balance)
        ).scalar_one()

    return TokenDrawOut(token_id=token_id, points_awarded=points_awarded, points_balance=new_balance)


@router.get("/pickups", response_model=list[PendingPickupOut])
def list_pending_pickups(
    region_id: int | None = None,
    current_user: CurrentUser = Depends(require_roles("waste_bank", "authorized")),
) -> list[PendingPickupOut]:
    """Submissions still awaiting collection. waste_bank admins only see
    their assigned region(s); authorized sees everything (optionally
    filtered via `?region_id=`)."""
    if current_user.role == "waste_bank" and not current_user.region_ids:
        return []

    num_objects = (
        select(func.count(wastes.c.id))
        .where(wastes.c.submission_id == waste_submissions.c.id)
        .correlate(waste_submissions)
        .scalar_subquery()
    )

    query = (
        select(
            waste_submissions.c.id,
            waste_submissions.c.status,
            waste_submissions.c.created_at,
            users.c.id,
            users.c.name,
            users.c.address,
            users.c.region_id,
            regions.c.name,
            num_objects.label("num_objects"),
        )
        .select_from(
            waste_submissions.join(users, users.c.id == waste_submissions.c.user_id).outerjoin(
                regions, regions.c.id == users.c.region_id
            )
        )
        .where(waste_submissions.c.status == "pending_pickup")
        .order_by(waste_submissions.c.created_at)
    )
    if current_user.role == "waste_bank":
        query = query.where(users.c.region_id.in_(current_user.region_ids))
    elif region_id is not None:
        query = query.where(users.c.region_id == region_id)

    with get_engine().connect() as conn:
        rows = conn.execute(query).all()

    return [
        PendingPickupOut(
            submission_id=row[0],
            status=row[1],
            created_at=row[2],
            num_objects=row[8],
            user_id=row[3],
            user_name=row[4],
            user_address=row[5],
            region_id=row[6],
            region_name=row[7],
        )
        for row in rows
    ]


@router.get("/history", response_model=list[WasteRecordOut])
def list_waste_history(
    status: str | None = None,
    region_id: int | None = None,
    user_id: int | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[WasteRecordOut]:
    """All waste submissions regardless of status — `pending_choice`,
    `pending_pickup`, `pending_dropoff`, `collected`, and `dropped_off`
    alike — not just what's still outstanding.

    Visibility is role-scoped:
      - `user`: only the caller's own submissions.
      - `waste_bank`: submissions from users in the admin's assigned
        region(s), both still-pending and already collected/dropped off.
      - `authorized`: everything, optionally filtered via `?region_id=`,
        `?user_id=`, and/or `?status=`.
    """
    valid_statuses = {"pending_choice", "pending_pickup", "pending_dropoff", "collected", "dropped_off"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status filter. Must be one of {sorted(valid_statuses)}"
        )

    if current_user.role == "waste_bank" and not current_user.region_ids:
        return []

    num_objects = (
        select(func.count(wastes.c.id))
        .where(wastes.c.submission_id == waste_submissions.c.id)
        .correlate(waste_submissions)
        .scalar_subquery()
    )

    query = (
        select(
            waste_submissions.c.id,
            waste_submissions.c.status,
            waste_submissions.c.delivery_method,
            waste_submissions.c.created_at,
            waste_submissions.c.collected_at,
            users.c.id,
            users.c.name,
            users.c.address,
            users.c.region_id,
            regions.c.name,
            num_objects.label("num_objects"),
        )
        .select_from(
            waste_submissions.join(users, users.c.id == waste_submissions.c.user_id).outerjoin(
                regions, regions.c.id == users.c.region_id
            )
        )
        .order_by(waste_submissions.c.created_at.desc())
    )

    if current_user.role == "user":
        query = query.where(waste_submissions.c.user_id == current_user.id)
    elif current_user.role == "waste_bank":
        if region_id is not None and region_id not in current_user.region_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this region")
        query = query.where(users.c.region_id.in_(current_user.region_ids))
    else:  # authorized
        if region_id is not None:
            query = query.where(users.c.region_id == region_id)
        if user_id is not None:
            query = query.where(waste_submissions.c.user_id == user_id)

    if status is not None:
        query = query.where(waste_submissions.c.status == status)

    with get_engine().connect() as conn:
        rows = conn.execute(query).all()

    return [
        WasteRecordOut(
            submission_id=row[0],
            status=row[1],
            delivery_method=row[2],
            created_at=row[3],
            collected_at=row[4],
            num_objects=row[10],
            user_id=row[5],
            user_name=row[6],
            user_address=row[7],
            region_id=row[8],
            region_name=row[9],
        )
        for row in rows
    ]


@router.post("/pickups/{submission_id}/collect", response_model=WasteSubmissionOut)
def collect_pickup(
    submission_id: int,
    current_user: CurrentUser = Depends(require_roles("waste_bank", "authorized")),
) -> WasteSubmissionOut:
    with get_engine().begin() as conn:
        row = conn.execute(
            select(waste_submissions.c.status, users.c.region_id)
            .select_from(waste_submissions.join(users, users.c.id == waste_submissions.c.user_id))
            .where(waste_submissions.c.id == submission_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        _current_status, region_id = row

        if current_user.role == "waste_bank" and region_id not in current_user.region_ids:
            raise HTTPException(status_code=403, detail="Not authorized to collect for this region")

        result = conn.execute(
            update(waste_submissions)
            .where(waste_submissions.c.id == submission_id, waste_submissions.c.status == "pending_pickup")
            .values(status="collected", collected_by=current_user.id, collected_at=datetime.now(timezone.utc))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Already collected")

    return _load_submission(submission_id)


@router.post("/dropoffs/{submission_id}/confirm", response_model=WasteSubmissionOut)
def confirm_dropoff(
    submission_id: int,
    current_user: CurrentUser = Depends(require_roles("waste_bank", "authorized")),
) -> WasteSubmissionOut:
    """Marks a self-dropoff submission "dropped_off".

    This is meant to be hit automatically by the waste_bank's intake
    system (e.g. a QR/badge scan at the bin) the moment a user physically
    drops their waste off — not a manual button a staff member clicks.
    For now this is just the DB-side bookkeeping so that trigger has
    somewhere to land; wiring up the actual device/kiosk call is a
    follow-up.
    """
    with get_engine().begin() as conn:
        row = conn.execute(
            select(waste_submissions.c.delivery_method, waste_submissions.c.dropoff_waste_bank_id).where(
                waste_submissions.c.id == submission_id
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        delivery_method, dropoff_waste_bank_id = row

        if delivery_method != "self_dropoff":
            raise HTTPException(status_code=400, detail="Submission wasn't set up for self-dropoff")

        if current_user.role == "waste_bank" and dropoff_waste_bank_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to confirm drop-off for this submission")

        result = conn.execute(
            update(waste_submissions)
            .where(waste_submissions.c.id == submission_id, waste_submissions.c.status == "pending_dropoff")
            .values(status="dropped_off", collected_by=current_user.id, collected_at=datetime.now(timezone.utc))
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Already dropped off")

    return _load_submission(submission_id)


def _load_submission(submission_id: int) -> WasteSubmissionOut:
    with get_engine().connect() as conn:
        submission = conn.execute(
            select(
                waste_submissions.c.id,
                waste_submissions.c.user_id,
                waste_submissions.c.created_at,
                waste_submissions.c.status,
                waste_submissions.c.delivery_method,
                waste_submissions.c.scheduled_pickup_at,
                waste_submissions.c.dropoff_waste_bank_id,
                waste_submissions.c.segmented_image_path,
                waste_submissions.c.results_grid_path,
            ).where(waste_submissions.c.id == submission_id)
        ).first()
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")

        waste_rows = conn.execute(
            select(
                wastes.c.obj_index,
                wastes.c.coco_label,
                wastes.c.segmentation_score,
                wastes.c.bbox_x1,
                wastes.c.bbox_y1,
                wastes.c.bbox_x2,
                wastes.c.bbox_y2,
                wastes.c.waste_label,
                wastes.c.waste_confidence,
                wastes.c.weight_kg,
                waste_tokens.c.id,
                waste_tokens.c.start_range,
                waste_tokens.c.end_range,
                waste_tokens.c.used,
            )
            .select_from(wastes.join(waste_tokens, waste_tokens.c.waste_id == wastes.c.id))
            .where(wastes.c.submission_id == submission_id)
            .order_by(wastes.c.obj_index)
        ).all()

    objects = [
        WasteObjectPrediction(
            index=row[0],
            coco_label=row[1],
            segmentation_score=row[2],
            bbox_xyxy=(row[3], row[4], row[5], row[6]),
            waste_label=row[7],
            waste_confidence=row[8],
            weight_kg=row[9],
            token_id=row[10],
            start_range=row[11],
            end_range=row[12],
            used=row[13],
        )
        for row in waste_rows
    ]

    return WasteSubmissionOut(
        id=submission[0],
        user_id=submission[1],
        created_at=submission[2],
        num_objects=len(objects),
        objects=objects,
        status=submission[3],
        delivery_method=submission[4],
        scheduled_pickup_at=submission[5],
        dropoff_waste_bank_id=submission[6],
        segmented_image_path=submission[7],
        results_grid_path=submission[8],
    )
