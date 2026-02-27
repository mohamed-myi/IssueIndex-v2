"""Intent CRUD operations and intent vector recalculation orchestration."""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from gim_database.models.profiles import UserProfile
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.errors import IntentAlreadyExistsError, IntentNotFoundError
from gim_backend.services.onboarding_service import mark_onboarding_in_progress
from gim_backend.services.profile_core_service import get_or_create_profile
from gim_backend.services.profile_embedding_service import (
    calculate_combined_vector,
    finalize_profile_recalculation,
    mark_profile_recalculation_started,
    reset_profile_recalculation,
)
from gim_backend.services.profile_models import IntentProfile, IntentReembedInput
from gim_backend.services.profile_validation import (
    validate_experience_level,
    validate_languages,
    validate_stack_areas,
)
from gim_backend.services.vector_generation import generate_intent_vector_with_retry

logger = logging.getLogger(__name__)

AsyncProfileGetter = Callable[[AsyncSession, UUID], Awaitable[UserProfile]]
AsyncOnboardingMarker = Callable[[AsyncSession, UserProfile], Awaitable[None]]
AsyncIntentVectorGenerator = Callable[[list[str], str], Awaitable[object | None]]
AsyncCombinedVectorCalculator = Callable[..., Awaitable[object | None]]
IntentMutator = Callable[[], IntentReembedInput]


def _intent_reembed_log_messages(operation_label: str, user_id: UUID) -> tuple[str, str, str]:
    if operation_label == "create":
        return (
            f"Generating intent vector for user {user_id}",
            f"Intent vector generated for user {user_id}",
            f"Intent vector generation failed for user {user_id}; profile saved without vector",
        )

    return (
        f"Regenerating intent vector for user {user_id}",
        f"Intent vector regenerated for user {user_id}",
        f"Intent vector regeneration failed for user {user_id}",
    )


async def _run_intent_mutation_with_recalculation(
    db: AsyncSession,
    profile: UserProfile,
    user_id: UUID,
    *,
    operation_label: str,
    mutate_profile: IntentMutator,
    generate_intent_vector_with_retry_fn: AsyncIntentVectorGenerator,
    calculate_combined_vector_fn: AsyncCombinedVectorCalculator,
) -> None:
    mark_profile_recalculation_started(profile)
    reembed_input = mutate_profile()
    await db.commit()

    try:
        if reembed_input is not None:
            stack_areas, text = reembed_input
            start_log, success_log, failure_log = _intent_reembed_log_messages(operation_label, user_id)
            logger.info(start_log)
            intent_vector = await generate_intent_vector_with_retry_fn(stack_areas, text)
            profile.intent_vector = intent_vector

            await finalize_profile_recalculation(
                profile,
                calculate_combined_vector_fn=calculate_combined_vector_fn,
            )

            if intent_vector is not None:
                logger.info(success_log)
            else:
                logger.warning(failure_log)
            return

        logger.info(f"Recalculating combined vector after intent deletion for user {user_id}")
        await finalize_profile_recalculation(
            profile,
            calculate_combined_vector_fn=calculate_combined_vector_fn,
        )
    finally:
        if profile.is_calculating:
            reset_profile_recalculation(profile)


async def create_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None = None,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
    mark_onboarding_in_progress_fn: AsyncOnboardingMarker | None = None,
    generate_intent_vector_with_retry_fn: AsyncIntentVectorGenerator | None = None,
    calculate_combined_vector_fn: AsyncCombinedVectorCalculator | None = None,
) -> UserProfile:
    """Languages stored in preferred_languages for Stage 1 SQL filtering."""
    validate_languages(languages)
    validate_stack_areas(stack_areas)
    validate_experience_level(experience_level)

    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    onboarding_marker = (
        mark_onboarding_in_progress
        if mark_onboarding_in_progress_fn is None
        else mark_onboarding_in_progress_fn
    )
    intent_vector_generator = (
        generate_intent_vector_with_retry
        if generate_intent_vector_with_retry_fn is None
        else generate_intent_vector_with_retry_fn
    )
    combined_vector_calculator = (
        calculate_combined_vector if calculate_combined_vector_fn is None else calculate_combined_vector_fn
    )

    profile = await profile_getter(db, user_id)

    if profile.intent_text is not None:
        raise IntentAlreadyExistsError("Intent already exists. Use PATCH to update or DELETE first.")

    await onboarding_marker(db, profile)

    await _run_intent_mutation_with_recalculation(
        db,
        profile,
        user_id,
        operation_label="create",
        mutate_profile=lambda: _apply_create_intent_fields(
            profile,
            languages=languages,
            stack_areas=stack_areas,
            text=text,
            experience_level=experience_level,
        ),
        generate_intent_vector_with_retry_fn=intent_vector_generator,
        calculate_combined_vector_fn=combined_vector_calculator,
    )

    await db.commit()
    await db.refresh(profile)
    return profile


async def put_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None = None,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
    mark_onboarding_in_progress_fn: AsyncOnboardingMarker | None = None,
    generate_intent_vector_with_retry_fn: AsyncIntentVectorGenerator | None = None,
    calculate_combined_vector_fn: AsyncCombinedVectorCalculator | None = None,
) -> tuple[UserProfile, bool]:
    validate_languages(languages)
    validate_stack_areas(stack_areas)
    validate_experience_level(experience_level)

    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    onboarding_marker = (
        mark_onboarding_in_progress
        if mark_onboarding_in_progress_fn is None
        else mark_onboarding_in_progress_fn
    )
    intent_vector_generator = (
        generate_intent_vector_with_retry
        if generate_intent_vector_with_retry_fn is None
        else generate_intent_vector_with_retry_fn
    )
    combined_vector_calculator = (
        calculate_combined_vector if calculate_combined_vector_fn is None else calculate_combined_vector_fn
    )

    profile = await profile_getter(db, user_id)

    created = profile.intent_text is None
    if created:
        created_profile = await create_intent(
            db=db,
            user_id=user_id,
            languages=languages,
            stack_areas=stack_areas,
            text=text,
            experience_level=experience_level,
            get_or_create_profile_fn=profile_getter,
            mark_onboarding_in_progress_fn=onboarding_marker,
            generate_intent_vector_with_retry_fn=intent_vector_generator,
            calculate_combined_vector_fn=combined_vector_calculator,
        )
        return created_profile, True

    await onboarding_marker(db, profile)

    current_stack_areas = profile.intent_stack_areas or []
    current_text = profile.intent_text or ""

    needs_reembed = current_stack_areas != stack_areas or current_text != text

    profile.preferred_languages = languages
    profile.intent_stack_areas = stack_areas
    profile.intent_text = text
    profile.intent_experience = experience_level

    if needs_reembed:
        await _run_intent_mutation_with_recalculation(
            db,
            profile,
            user_id,
            operation_label="put",
            mutate_profile=lambda: (stack_areas, text),
            generate_intent_vector_with_retry_fn=intent_vector_generator,
            calculate_combined_vector_fn=combined_vector_calculator,
        )

    await db.commit()
    await db.refresh(profile)
    return profile, False


async def get_intent(
    db: AsyncSession,
    user_id: UUID,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
) -> IntentProfile | None:
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    profile = await profile_getter(db, user_id)

    if profile.intent_text is None:
        return None

    vector_status = "ready" if profile.intent_vector else None

    return IntentProfile(
        languages=profile.preferred_languages or [],
        stack_areas=profile.intent_stack_areas or [],
        text=profile.intent_text,
        experience_level=profile.intent_experience,
        vector_status=vector_status,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


async def update_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str] | None = None,
    stack_areas: list[str] | None = None,
    text: str | None = None,
    experience_level: str | None = None,
    _experience_level_provided: bool = False,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
    generate_intent_vector_with_retry_fn: AsyncIntentVectorGenerator | None = None,
    calculate_combined_vector_fn: AsyncCombinedVectorCalculator | None = None,
) -> UserProfile:
    """
    The _experience_level_provided flag distinguishes omitted from explicitly null.
    Only text and stack_areas changes trigger re-embedding.
    """
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    intent_vector_generator = (
        generate_intent_vector_with_retry
        if generate_intent_vector_with_retry_fn is None
        else generate_intent_vector_with_retry_fn
    )
    combined_vector_calculator = (
        calculate_combined_vector if calculate_combined_vector_fn is None else calculate_combined_vector_fn
    )

    profile = await profile_getter(db, user_id)

    if profile.intent_text is None:
        raise IntentNotFoundError("No intent exists. Use POST to create first.")

    needs_reembed = False

    if languages is not None:
        validate_languages(languages)
        profile.preferred_languages = languages

    if stack_areas is not None:
        validate_stack_areas(stack_areas)
        profile.intent_stack_areas = stack_areas
        needs_reembed = True

    if text is not None:
        profile.intent_text = text
        needs_reembed = True

    if _experience_level_provided:
        validate_experience_level(experience_level)
        profile.intent_experience = experience_level

    if needs_reembed:
        await _run_intent_mutation_with_recalculation(
            db,
            profile,
            user_id,
            operation_label="update",
            mutate_profile=lambda: (profile.intent_stack_areas or [], profile.intent_text or ""),
            generate_intent_vector_with_retry_fn=intent_vector_generator,
            calculate_combined_vector_fn=combined_vector_calculator,
        )

    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_intent(
    db: AsyncSession,
    user_id: UUID,
    *,
    get_or_create_profile_fn: AsyncProfileGetter | None = None,
    generate_intent_vector_with_retry_fn: AsyncIntentVectorGenerator | None = None,
    calculate_combined_vector_fn: AsyncCombinedVectorCalculator | None = None,
) -> bool:
    """Also clears preferred_languages since they originate from intent."""
    profile_getter = get_or_create_profile if get_or_create_profile_fn is None else get_or_create_profile_fn
    intent_vector_generator = (
        generate_intent_vector_with_retry
        if generate_intent_vector_with_retry_fn is None
        else generate_intent_vector_with_retry_fn
    )
    combined_vector_calculator = (
        calculate_combined_vector if calculate_combined_vector_fn is None else calculate_combined_vector_fn
    )

    profile = await profile_getter(db, user_id)

    if profile.intent_text is None:
        return False

    await _run_intent_mutation_with_recalculation(
        db,
        profile,
        user_id,
        operation_label="delete",
        mutate_profile=lambda: _apply_delete_intent_fields(profile),
        generate_intent_vector_with_retry_fn=intent_vector_generator,
        calculate_combined_vector_fn=combined_vector_calculator,
    )

    await db.commit()
    await db.refresh(profile)
    return True


def _apply_create_intent_fields(
    profile: UserProfile,
    *,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None,
) -> IntentReembedInput:
    profile.preferred_languages = languages
    profile.intent_stack_areas = stack_areas
    profile.intent_text = text
    profile.intent_experience = experience_level
    return stack_areas, text


def _apply_delete_intent_fields(profile: UserProfile) -> IntentReembedInput:
    profile.preferred_languages = None
    profile.intent_stack_areas = None
    profile.intent_text = None
    profile.intent_experience = None
    profile.intent_vector = None
    return None


__all__ = [
    "create_intent",
    "delete_intent",
    "get_intent",
    "put_intent",
    "update_intent",
]
