"""Core profile CRUD/read-model operations shared across profile services."""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from gim_database.models.profiles import UserProfile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.services.cloud_tasks_service import cancel_user_tasks
from gim_backend.services.profile_access import get_or_create_profile_record
from gim_backend.services.profile_models import (
    FullProfile,
    GitHubData,
    GitHubSource,
    IntentData,
    IntentSource,
    ProfilePreferences,
    ProfileSources,
    ResumeData,
    ResumeSource,
)
from gim_backend.services.profile_validation import calculate_optimization_percent

logger = logging.getLogger(__name__)

AsyncProfileGetter = Callable[[AsyncSession, UUID], Awaitable[UserProfile]]
AsyncTaskCanceler = Callable[[UUID], Awaitable[int]]


async def get_or_create_profile(
    db: AsyncSession,
    user_id: UUID,
) -> UserProfile:
    return await get_or_create_profile_record(db, user_id)


async def get_full_profile(
    db: AsyncSession,
    user_id: UUID,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
) -> FullProfile:
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    profile = await profile_getter(db, user_id)

    intent_populated = profile.intent_text is not None
    intent_data = None
    if intent_populated:
        intent_data = IntentData(
            languages=profile.preferred_languages or [],
            stack_areas=profile.intent_stack_areas or [],
            text=profile.intent_text,
            experience_level=profile.intent_experience,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        )

    resume_populated = profile.resume_skills is not None
    resume_data = None
    if resume_populated:
        resume_data = ResumeData(
            skills=profile.resume_skills or [],
            job_titles=profile.resume_job_titles or [],
            uploaded_at=profile.resume_uploaded_at.isoformat() if profile.resume_uploaded_at else None,
        )

    github_populated = profile.github_username is not None
    github_data = None
    if github_populated:
        github_data = GitHubData(
            username=profile.github_username,
            languages=profile.github_languages or [],
            topics=profile.github_topics or [],
            fetched_at=profile.github_fetched_at.isoformat() if profile.github_fetched_at else None,
        )

    intent_vector_status = "ready" if profile.intent_vector else None
    resume_vector_status = "ready" if profile.resume_vector else None
    github_vector_status = "ready" if profile.github_vector else None
    combined_vector_status = "ready" if profile.combined_vector else None

    return FullProfile(
        user_id=str(profile.user_id),
        optimization_percent=calculate_optimization_percent(profile),
        combined_vector_status=combined_vector_status,
        is_calculating=profile.is_calculating,
        onboarding_status=profile.onboarding_status,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        sources=ProfileSources(
            intent=IntentSource(
                populated=intent_populated,
                vector_status=intent_vector_status,
                data=intent_data,
            ),
            resume=ResumeSource(
                populated=resume_populated,
                vector_status=resume_vector_status,
                data=resume_data,
            ),
            github=GitHubSource(
                populated=github_populated,
                vector_status=github_vector_status,
                data=github_data,
            ),
        ),
        preferences=ProfilePreferences(
            preferred_languages=profile.preferred_languages or [],
            preferred_topics=profile.preferred_topics or [],
            min_heat_threshold=profile.min_heat_threshold,
        ),
    )


async def delete_profile(
    db: AsyncSession,
    user_id: UUID,
    *,
    cancel_user_tasks_fn: AsyncTaskCanceler | None = None,
) -> bool:
    """Resets all fields to defaults; does not delete the row. Cancels pending Cloud Tasks."""
    statement = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.exec(statement)
    profile = result.first()

    if profile is None:
        return False

    task_canceler = cancel_user_tasks if cancel_user_tasks_fn is None else cancel_user_tasks_fn
    cancelled_count = await task_canceler(user_id)
    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} pending Cloud Tasks for user {user_id}")

    _reset_profile_fields(profile)

    await db.commit()
    await db.refresh(profile)
    return True


def _reset_profile_fields(profile: UserProfile) -> None:
    profile.intent_vector = None
    profile.resume_vector = None
    profile.github_vector = None
    profile.combined_vector = None

    profile.intent_stack_areas = None
    profile.intent_text = None
    profile.intent_experience = None

    profile.resume_skills = None
    profile.resume_job_titles = None
    profile.resume_raw_entities = None
    profile.resume_uploaded_at = None

    profile.github_username = None
    profile.github_languages = None
    profile.github_topics = None
    profile.github_data = None
    profile.github_fetched_at = None

    profile.preferred_languages = None
    profile.preferred_topics = None
    profile.min_heat_threshold = 0.6

    profile.is_calculating = False
    profile.onboarding_status = "not_started"
    profile.onboarding_completed_at = None


__all__ = [
    "delete_profile",
    "get_full_profile",
    "get_or_create_profile",
]
