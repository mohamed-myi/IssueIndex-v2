"""
Profile service for CRUD operations on user profiles, intents, and preferences.
"""
import logging
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.profiles import UserProfile
from src.services.profile_embedding_service import calculate_combined_vector
from src.services.vector_generation import generate_intent_vector_with_retry
from src.services.onboarding_service import mark_onboarding_in_progress
from src.services.cloud_tasks_service import cancel_user_tasks

import sys
from pathlib import Path

shared_src = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "shared" / "src"
if str(shared_src) not in sys.path:
    sys.path.insert(0, str(shared_src))

from constants import PROFILE_LANGUAGES, STACK_AREAS

logger = logging.getLogger(__name__)


from src.core.errors import (
    InvalidTaxonomyValueError,
    IntentAlreadyExistsError,
    IntentNotFoundError,
)


VALID_EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]


def validate_languages(languages: list[str]) -> None:
    for lang in languages:
        if lang not in PROFILE_LANGUAGES:
            raise InvalidTaxonomyValueError(
                field="language",
                invalid_value=lang,
                valid_options=PROFILE_LANGUAGES,
            )


def validate_stack_areas(areas: list[str]) -> None:
    valid_areas = list(STACK_AREAS.keys())
    for area in areas:
        if area not in valid_areas:
            raise InvalidTaxonomyValueError(
                field="stack_area",
                invalid_value=area,
                valid_options=valid_areas,
            )


def validate_experience_level(level: str | None) -> None:
    if level is not None and level not in VALID_EXPERIENCE_LEVELS:
        raise InvalidTaxonomyValueError(
            field="experience_level",
            invalid_value=level,
            valid_options=VALID_EXPERIENCE_LEVELS,
        )


def calculate_optimization_percent(profile: UserProfile) -> int:
    """Weights: intent 50, resume 30, github 20."""
    optimization = 0
    
    if profile.intent_text:
        optimization += 50
    
    if profile.resume_skills:
        optimization += 30
    
    if profile.github_username:
        optimization += 20
    
    return optimization


async def get_or_create_profile(
    db: AsyncSession,
    user_id: UUID,
) -> UserProfile:
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


async def get_full_profile(
    db: AsyncSession,
    user_id: UUID,
) -> dict:
    profile = await get_or_create_profile(db, user_id)
    
    intent_populated = profile.intent_text is not None
    intent_data = None
    if intent_populated:
        intent_data = {
            "languages": profile.preferred_languages or [],
            "stack_areas": profile.intent_stack_areas or [],
            "text": profile.intent_text,
            "experience_level": profile.intent_experience,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
    
    resume_populated = profile.resume_skills is not None
    resume_data = None
    if resume_populated:
        resume_data = {
            "skills": profile.resume_skills or [],
            "job_titles": profile.resume_job_titles or [],
            "uploaded_at": profile.resume_uploaded_at.isoformat() if profile.resume_uploaded_at else None,
        }
    
    github_populated = profile.github_username is not None
    github_data = None
    if github_populated:
        github_data = {
            "username": profile.github_username,
            "languages": profile.github_languages or [],
            "topics": profile.github_topics or [],
            "fetched_at": profile.github_fetched_at.isoformat() if profile.github_fetched_at else None,
        }
    
    intent_vector_status = "ready" if profile.intent_vector else None
    resume_vector_status = "ready" if profile.resume_vector else None
    github_vector_status = "ready" if profile.github_vector else None
    combined_vector_status = "ready" if profile.combined_vector else None
    
    return {
        "user_id": str(profile.user_id),
        "optimization_percent": calculate_optimization_percent(profile),
        "combined_vector_status": combined_vector_status,
        "is_calculating": profile.is_calculating,
        "onboarding_status": profile.onboarding_status,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "sources": {
            "intent": {
                "populated": intent_populated,
                "vector_status": intent_vector_status,
                "data": intent_data,
            },
            "resume": {
                "populated": resume_populated,
                "vector_status": resume_vector_status,
                "data": resume_data,
            },
            "github": {
                "populated": github_populated,
                "vector_status": github_vector_status,
                "data": github_data,
            },
        },
        "preferences": {
            "preferred_languages": profile.preferred_languages or [],
            "preferred_topics": profile.preferred_topics or [],
            "min_heat_threshold": profile.min_heat_threshold,
        },
    }


async def delete_profile(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    """Resets all fields to defaults; does not delete the row. Cancels pending Cloud Tasks."""
    statement = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.exec(statement)
    profile = result.first()
    
    if profile is None:
        return False
    
    cancelled_count = await cancel_user_tasks(user_id)
    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} pending Cloud Tasks for user {user_id}")
    
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
    
    await db.commit()
    await db.refresh(profile)
    return True


async def create_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str],
    stack_areas: list[str],
    text: str,
    experience_level: str | None = None,
) -> UserProfile:
    """Languages stored in preferred_languages for Stage 1 SQL filtering."""
    validate_languages(languages)
    validate_stack_areas(stack_areas)
    validate_experience_level(experience_level)
    
    profile = await get_or_create_profile(db, user_id)
    
    if profile.intent_text is not None:
        raise IntentAlreadyExistsError(
            "Intent already exists. Use PATCH to update or DELETE first."
        )
    
    await mark_onboarding_in_progress(db, profile)
    
    profile.preferred_languages = languages
    profile.intent_stack_areas = stack_areas
    profile.intent_text = text
    profile.intent_experience = experience_level
    profile.is_calculating = True
    await db.commit()
    
    try:
        logger.info(f"Generating intent vector for user {user_id}")
        intent_vector = await generate_intent_vector_with_retry(stack_areas, text)
        profile.intent_vector = intent_vector
        
        combined = await calculate_combined_vector(
            intent_vector=intent_vector,
            resume_vector=profile.resume_vector,
            github_vector=profile.github_vector,
        )
        profile.combined_vector = combined
        
        if intent_vector is not None:
            logger.info(f"Intent vector generated for user {user_id}")
        else:
            logger.warning(f"Intent vector generation failed for user {user_id}; profile saved without vector")
    finally:
        profile.is_calculating = False
    
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
) -> tuple[UserProfile, bool]:
    validate_languages(languages)
    validate_stack_areas(stack_areas)
    validate_experience_level(experience_level)

    profile = await get_or_create_profile(db, user_id)

    created = profile.intent_text is None
    if created:
        created_profile = await create_intent(
            db=db,
            user_id=user_id,
            languages=languages,
            stack_areas=stack_areas,
            text=text,
            experience_level=experience_level,
        )
        return created_profile, True

    await mark_onboarding_in_progress(db, profile)

    current_stack_areas = profile.intent_stack_areas or []
    current_text = profile.intent_text or ""

    needs_reembed = current_stack_areas != stack_areas or current_text != text

    profile.preferred_languages = languages
    profile.intent_stack_areas = stack_areas
    profile.intent_text = text
    profile.intent_experience = experience_level

    if needs_reembed:
        profile.is_calculating = True
        await db.commit()

        try:
            logger.info(f"Regenerating intent vector for user {user_id}")
            intent_vector = await generate_intent_vector_with_retry(stack_areas, text)
            profile.intent_vector = intent_vector

            combined = await calculate_combined_vector(
                intent_vector=intent_vector,
                resume_vector=profile.resume_vector,
                github_vector=profile.github_vector,
            )
            profile.combined_vector = combined

            if intent_vector is not None:
                logger.info(f"Intent vector regenerated for user {user_id}")
            else:
                logger.warning(f"Intent vector regeneration failed for user {user_id}")
        finally:
            profile.is_calculating = False

    await db.commit()
    await db.refresh(profile)
    return profile, False


async def get_intent(
    db: AsyncSession,
    user_id: UUID,
) -> dict | None:
    profile = await get_or_create_profile(db, user_id)
    
    if profile.intent_text is None:
        return None
    
    vector_status = "ready" if profile.intent_vector else None
    
    return {
        "languages": profile.preferred_languages or [],
        "stack_areas": profile.intent_stack_areas or [],
        "text": profile.intent_text,
        "experience_level": profile.intent_experience,
        "vector_status": vector_status,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


async def update_intent(
    db: AsyncSession,
    user_id: UUID,
    languages: list[str] | None = None,
    stack_areas: list[str] | None = None,
    text: str | None = None,
    experience_level: str | None = None,
    _experience_level_provided: bool = False,
) -> UserProfile:
    """
    The _experience_level_provided flag distinguishes omitted from explicitly null.
    Only text and stack_areas changes trigger re-embedding.
    """
    profile = await get_or_create_profile(db, user_id)
    
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
        profile.is_calculating = True
        await db.commit()
        
        try:
            logger.info(f"Regenerating intent vector for user {user_id}")
            intent_vector = await generate_intent_vector_with_retry(
                profile.intent_stack_areas or [],
                profile.intent_text or "",
            )
            profile.intent_vector = intent_vector
            
            combined = await calculate_combined_vector(
                intent_vector=intent_vector,
                resume_vector=profile.resume_vector,
                github_vector=profile.github_vector,
            )
            profile.combined_vector = combined
            
            if intent_vector is not None:
                logger.info(f"Intent vector regenerated for user {user_id}")
            else:
                logger.warning(f"Intent vector regeneration failed for user {user_id}")
        finally:
            profile.is_calculating = False
    
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_intent(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    """Also clears preferred_languages since they originate from intent."""
    profile = await get_or_create_profile(db, user_id)
    
    if profile.intent_text is None:
        return False
    
    profile.is_calculating = True
    await db.commit()
    
    try:
        profile.preferred_languages = None
        profile.intent_stack_areas = None
        profile.intent_text = None
        profile.intent_experience = None
        profile.intent_vector = None
        
        logger.info(f"Recalculating combined vector after intent deletion for user {user_id}")
        combined = await calculate_combined_vector(
            intent_vector=None,
            resume_vector=profile.resume_vector,
            github_vector=profile.github_vector,
        )
        profile.combined_vector = combined
    finally:
        profile.is_calculating = False
    
    await db.commit()
    await db.refresh(profile)
    return True


async def get_preferences(
    db: AsyncSession,
    user_id: UUID,
) -> dict:
    profile = await get_or_create_profile(db, user_id)
    
    return {
        "preferred_languages": profile.preferred_languages or [],
        "preferred_topics": profile.preferred_topics or [],
        "min_heat_threshold": profile.min_heat_threshold,
    }


async def update_preferences(
    db: AsyncSession,
    user_id: UUID,
    preferred_languages: list[str] | None = None,
    preferred_topics: list[str] | None = None,
    min_heat_threshold: float | None = None,
) -> UserProfile:
    profile = await get_or_create_profile(db, user_id)
    
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
