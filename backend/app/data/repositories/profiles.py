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
            risk_tolerance=payload.risk_tolerance,
            interest_tags=payload.interest_tags,
            excluded_sectors=payload.excluded_sectors,
            goals_note=payload.goals_note,
        )
        db.add(profile)
    else:
        profile.display_name = payload.display_name
        profile.base_currency = payload.base_currency
        profile.time_horizon = payload.time_horizon
        profile.investment_frequency = payload.investment_frequency
        if "risk_tolerance" in payload.model_fields_set:
            profile.risk_tolerance = payload.risk_tolerance
        if "interest_tags" in payload.model_fields_set:
            profile.interest_tags = payload.interest_tags
        if "excluded_sectors" in payload.model_fields_set:
            profile.excluded_sectors = payload.excluded_sectors
        if "goals_note" in payload.model_fields_set:
            profile.goals_note = payload.goals_note

    db.commit()
    db.refresh(profile)
    return profile
