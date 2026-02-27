
from gim_database.models.profiles import UserProfile
from gim_shared.constants import PROFILE_LANGUAGES, STACK_AREAS

from gim_backend.core.errors import InvalidTaxonomyValueError

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


__all__ = [
    "VALID_EXPERIENCE_LEVELS",
    "calculate_optimization_percent",
    "validate_experience_level",
    "validate_languages",
    "validate_stack_areas",
]
