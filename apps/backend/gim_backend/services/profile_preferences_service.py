
from collections.abc import Awaitable, Callable
from uuid import UUID

from gim_database.models.profiles import UserProfile
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.services.profile_core_service import get_or_create_profile
from gim_backend.services.profile_models import ProfilePreferences
from gim_backend.services.profile_validation import validate_languages

AsyncProfileGetter = Callable[[AsyncSession, UUID], Awaitable[UserProfile]]


async def get_preferences(
    db: AsyncSession,
    user_id: UUID,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
) -> ProfilePreferences:
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    profile = await profile_getter(db, user_id)

    return ProfilePreferences(
        preferred_languages=profile.preferred_languages or [],
        preferred_topics=profile.preferred_topics or [],
        min_heat_threshold=profile.min_heat_threshold,
    )


async def update_preferences(
    db: AsyncSession,
    user_id: UUID,
    preferred_languages: list[str] | None = None,
    preferred_topics: list[str] | None = None,
    min_heat_threshold: float | None = None,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
) -> UserProfile:
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    profile = await profile_getter(db, user_id)

    if preferred_languages is not None:
        validate_languages(preferred_languages)
        profile.preferred_languages = preferred_languages

    if preferred_topics is not None:
        profile.preferred_topics = preferred_topics

    if min_heat_threshold is not None:
        profile.min_heat_threshold = min_heat_threshold

    await db.commit()
    await db.refresh(profile)
    return profile


__all__ = [
    "get_preferences",
    "update_preferences",
]
