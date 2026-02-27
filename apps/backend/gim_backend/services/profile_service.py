"""Compatibility facade for profile services split into focused modules."""

from uuid import UUID

from gim_database.models.profiles import UserProfile
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.errors import (
    IntentAlreadyExistsError,
    IntentNotFoundError,
    InvalidTaxonomyValueError,
)
from gim_backend.services import profile_core_service as _profile_core_service
from gim_backend.services import profile_intent_service as _profile_intent_service
from gim_backend.services import profile_preferences_service as _profile_preferences_service
from gim_backend.services.cloud_tasks_service import cancel_user_tasks
from gim_backend.services.onboarding_service import mark_onboarding_in_progress
from gim_backend.services.profile_embedding_service import calculate_combined_vector
from gim_backend.services.profile_models import (
    FullProfile,
    GitHubData,
    GitHubSource,
    IntentData,
    IntentProfile,
    IntentReembedInput,
    IntentSource,
    ProfilePreferences,
    ProfileSources,
    ResumeData,
    ResumeSource,
)
from gim_backend.services.profile_validation import (
    VALID_EXPERIENCE_LEVELS,
    calculate_optimization_percent,
    validate_experience_level,
    validate_languages,
    validate_stack_areas,
)
from gim_backend.services.vector_generation import generate_intent_vector_with_retry


async def get_or_create_profile(
    db: AsyncSession,
    user_id: UUID,
) -> UserProfile:
    return await _profile_core_service.get_or_create_profile(db, user_id)


async def get_full_profile(
    db: AsyncSession,
    user_id: UUID,
) -> FullProfile:
    return await _profile_core_service.get_full_profile(
        db,
        user_id,
        get_or_create_profile_fn=get_or_create_profile,
    )


async def delete_profile(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    return await _profile_core_service.delete_profile(
        db,
        user_id,
        cancel_user_tasks_fn=cancel_user_tasks,
    )


async def create_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None = None,
) -> UserProfile:
    return await _profile_intent_service.create_intent(
        db=db,
        user_id=user_id,
        languages=languages,
        stack_areas=stack_areas,
        text=text,
        experience_level=experience_level,
        get_or_create_profile_fn=get_or_create_profile,
        mark_onboarding_in_progress_fn=mark_onboarding_in_progress,
        generate_intent_vector_with_retry_fn=generate_intent_vector_with_retry,
        calculate_combined_vector_fn=calculate_combined_vector,
    )


async def put_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None = None,
) -> tuple[UserProfile, bool]:
    return await _profile_intent_service.put_intent(
        db=db,
        user_id=user_id,
        languages=languages,
        stack_areas=stack_areas,
        text=text,
        experience_level=experience_level,
        get_or_create_profile_fn=get_or_create_profile,
        mark_onboarding_in_progress_fn=mark_onboarding_in_progress,
        generate_intent_vector_with_retry_fn=generate_intent_vector_with_retry,
        calculate_combined_vector_fn=calculate_combined_vector,
    )


async def get_intent(
    db: AsyncSession,
    user_id: UUID,
) -> IntentProfile | None:
    return await _profile_intent_service.get_intent(
        db,
        user_id,
        get_or_create_profile_fn=get_or_create_profile,
    )


async def update_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str] | None = None,
    stack_areas: list[str] | None = None,
    text: str | None = None,
    experience_level: str | None = None,
    _experience_level_provided: bool = False,
) -> UserProfile:
    return await _profile_intent_service.update_intent(
        db=db,
        user_id=user_id,
        languages=languages,
        stack_areas=stack_areas,
        text=text,
        experience_level=experience_level,
        _experience_level_provided=_experience_level_provided,
        get_or_create_profile_fn=get_or_create_profile,
        generate_intent_vector_with_retry_fn=generate_intent_vector_with_retry,
        calculate_combined_vector_fn=calculate_combined_vector,
    )


async def delete_intent(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    return await _profile_intent_service.delete_intent(
        db,
        user_id,
        get_or_create_profile_fn=get_or_create_profile,
        generate_intent_vector_with_retry_fn=generate_intent_vector_with_retry,
        calculate_combined_vector_fn=calculate_combined_vector,
    )


async def get_preferences(
    db: AsyncSession,
    user_id: UUID,
) -> ProfilePreferences:
    return await _profile_preferences_service.get_preferences(
        db,
        user_id,
        get_or_create_profile_fn=get_or_create_profile,
    )


async def update_preferences(
    db: AsyncSession,
    user_id: UUID,
    preferred_languages: list[str] | None = None,
    preferred_topics: list[str] | None = None,
    min_heat_threshold: float | None = None,
) -> UserProfile:
    return await _profile_preferences_service.update_preferences(
        db=db,
        user_id=user_id,
        preferred_languages=preferred_languages,
        preferred_topics=preferred_topics,
        min_heat_threshold=min_heat_threshold,
        get_or_create_profile_fn=get_or_create_profile,
    )


__all__ = [
    "FullProfile",
    "GitHubData",
    "GitHubSource",
    "IntentAlreadyExistsError",
    "IntentData",
    "IntentNotFoundError",
    "IntentProfile",
    "IntentReembedInput",
    "IntentSource",
    "InvalidTaxonomyValueError",
    "ProfilePreferences",
    "ProfileSources",
    "ResumeData",
    "ResumeSource",
    "VALID_EXPERIENCE_LEVELS",
    "calculate_combined_vector",
    "calculate_optimization_percent",
    "cancel_user_tasks",
    "create_intent",
    "delete_intent",
    "delete_profile",
    "generate_intent_vector_with_retry",
    "get_full_profile",
    "get_intent",
    "get_or_create_profile",
    "get_preferences",
    "mark_onboarding_in_progress",
    "put_intent",
    "update_intent",
    "update_preferences",
    "validate_experience_level",
    "validate_languages",
    "validate_stack_areas",
]
