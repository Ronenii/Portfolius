from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.data.database import get_db
from app.data.repositories.profiles import get_profile_by_user_id, upsert_profile
from app.schemas.profile import ProfileRequest, ProfileResponse

router = APIRouter(tags=["profile"])


@router.get("/api/v1/profile", response_model=ProfileResponse)
def read_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    profile = get_profile_by_user_id(db, current_user.user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return ProfileResponse.model_validate(profile)


@router.put("/api/v1/profile", response_model=ProfileResponse)
def save_profile(
    payload: ProfileRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    profile = upsert_profile(db, current_user.user_id, payload)
    return ProfileResponse.model_validate(profile)
