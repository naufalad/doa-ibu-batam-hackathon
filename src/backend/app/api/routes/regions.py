"""Region catalog — backs signup/admin-provisioning dropdowns and the
region scoping used by waste_bank pickups."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import require_roles
from app.db import get_engine, regions as regions_table
from app.schemas.region import RegionCreate, RegionOut

router = APIRouter(prefix="/regions", tags=["regions"])


# Public (no auth) — a new user picks their region on the signup form
# before they have any credentials to authenticate with.
@router.get("", response_model=list[RegionOut])
def list_regions() -> list[RegionOut]:
    with get_engine().connect() as conn:
        rows = conn.execute(select(regions_table.c.id, regions_table.c.name).order_by(regions_table.c.name))
        return [RegionOut(id=row[0], name=row[1]) for row in rows]


@router.post("", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
def create_region(
    payload: RegionCreate,
    _current_user=Depends(require_roles("authorized")),
) -> RegionOut:
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                insert(regions_table).values(name=payload.name).returning(regions_table.c.id, regions_table.c.name)
            ).first()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Region already exists") from exc
    return RegionOut(id=row[0], name=row[1])
