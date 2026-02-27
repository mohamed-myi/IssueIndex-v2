
from __future__ import annotations

from uuid import UUID

from gim_database.models.profiles import UserProfile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_or_create_profile_record(
    db: AsyncSession,
    user_id: UUID,
) -> UserProfile:
    """Fetches a user's profile row, creating defaults when absent.

    This helper intentionally preserves the current create semantics used across
    profile/onboarding/resume/github services: create -> commit -> refresh.
    """
    statement = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.exec(statement)
    profile = result.first()

    if profile is not None:
        return profile

    profile = UserProfile(
        user_id=user_id,
        min_heat_threshold=0.6,
        is_calculating=False,
        onboarding_status="not_started",
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


__all__ = ["get_or_create_profile_record"]
