from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Profile
from app.schemas.profile import ProfileRequest


def get_profile_by_user_id(db: Session, user_id: str) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))


def upsert_profile(db: Session, user_id: str, payload: ProfileRequest) -> Profile:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = Profile(
            user_id=user_id,
            display_name=payload.display_name,
            base_currency=payload.base_currency,
            time_horizon=payload.time_horizon,
            investment_frequency=payload.investment_frequency,
        )
        db.add(profile)
    else:
        profile.display_name = payload.display_name
        profile.base_currency = payload.base_currency
        profile.time_horizon = payload.time_horizon
        profile.investment_frequency = payload.investment_frequency

    db.commit()
    db.refresh(profile)
    return profile
