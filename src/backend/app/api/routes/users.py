"""User endpoints. Skeleton only — persistence is not wired up yet."""

from fastapi import APIRouter, HTTPException, status

from src.backend.app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserOut:
    # TODO: hash password, persist user, return the created record.
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int) -> UserOut:
    # TODO: fetch from database.
    raise HTTPException(status_code=501, detail="Not implemented yet")
