"""Onboarding API routes for tracking onboarding progress."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from gim_database.models.identity import Session, User
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.api.dependencies import get_db
from gim_backend.core.errors import InvalidTaxonomyValueError
from gim_backend.middleware.auth import require_auth
from gim_backend.services.onboarding_service import (
    CannotCompleteOnboardingError,
    OnboardingAlreadyCompletedError,
    complete_onboarding,
    get_onboarding_status,
    skip_onboarding,
    start_onboarding,
)
from gim_backend.services.profile_service import (
    put_intent as put_intent_service,
)
from gim_backend.services.profile_service import (
    update_preferences as update_preferences_service,
)
from gim_backend.services.recommendation_preview_service import (
    InvalidSourceError,
    get_preview_recommendations,
)

router = APIRouter()


class OnboardingStatusResponse(BaseModel):
    status: str
    completed_steps: list[str]
    available_steps: list[str]
    can_complete: bool


class OnboardingStartResponse(OnboardingStatusResponse):
    action: str


class OnboardingStepIntentInput(BaseModel):
    languages: list[str] = Field(..., min_length=1, max_length=10)
    stack_areas: list[str] = Field(..., min_length=1)
    text: str = Field(..., min_length=10, max_length=2000)
    experience_level: str | None = Field(default=None)


class OnboardingStepPreferencesInput(BaseModel):
    preferred_languages: list[str] | None = Field(default=None)
    preferred_topics: list[str] | None = Field(default=None)
    min_heat_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class OnboardingStepResponse(OnboardingStatusResponse):
    step: str
    payload: dict[str, Any]


class PreviewIssueResponse(BaseModel):
    node_id: str
    title: str
    repo_name: str
    primary_language: str | None
    q_score: float


class PreviewRecommendationsResponse(BaseModel):
    source: str | None
    issues: list[PreviewIssueResponse]


@router.get("/onboarding", response_model=OnboardingStatusResponse)
async def get_onboarding(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    user, _ = auth
    state = await get_onboarding_status(db, user.id)

    return OnboardingStatusResponse(
        status=state.status,
        completed_steps=state.completed_steps,
        available_steps=state.available_steps,
        can_complete=state.can_complete,
    )


@router.post("/onboarding/start", response_model=OnboardingStartResponse)
async def start_onboarding_route(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStartResponse:
    user, _ = auth

    try:
        result = await start_onboarding(db, user.id)
    except OnboardingAlreadyCompletedError as e:
        raise HTTPException(status_code=409, detail=str(e))

    state = result.state
    return OnboardingStartResponse(
        status=state.status,
        completed_steps=state.completed_steps,
        available_steps=state.available_steps,
        can_complete=state.can_complete,
        action=result.action,
    )


@router.patch("/onboarding/step/{step}", response_model=OnboardingStepResponse)
async def save_onboarding_step(
    step: str,
    request: Request,
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStepResponse:
    user, _ = auth

    if step not in ("welcome", "intent", "preferences"):
        raise HTTPException(status_code=400, detail="Invalid onboarding step")

    payload: dict[str, Any] = {}

    if step == "welcome":
        try:
            result = await start_onboarding(db, user.id)
        except OnboardingAlreadyCompletedError as e:
            raise HTTPException(status_code=409, detail=str(e))
        payload = {"action": result.action}

    if step == "intent":
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        try:
            intent = OnboardingStepIntentInput.model_validate(raw)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid intent payload")
        try:
            profile, created = await put_intent_service(
                db=db,
                user_id=user.id,
                languages=intent.languages,
                stack_areas=intent.stack_areas,
                text=intent.text,
                experience_level=intent.experience_level,
            )
        except InvalidTaxonomyValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        payload = {
            "created": created,
            "intent": {
                "languages": profile.preferred_languages or [],
                "stack_areas": profile.intent_stack_areas or [],
                "text": profile.intent_text or "",
                "experience_level": profile.intent_experience,
                "vector_status": "ready" if profile.intent_vector else None,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
            },
        }

    if step == "preferences":
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        try:
            preferences = OnboardingStepPreferencesInput.model_validate(raw)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid preferences payload")
        raw_body = preferences.model_dump(exclude_unset=True)
        if not raw_body:
            raise HTTPException(status_code=400, detail="No preferences fields provided")
        try:
            profile = await update_preferences_service(
                db=db,
                user_id=user.id,
                preferred_languages=preferences.preferred_languages,
                preferred_topics=preferences.preferred_topics,
                min_heat_threshold=preferences.min_heat_threshold,
            )
        except InvalidTaxonomyValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        payload = {
            "preferences": {
                "preferred_languages": profile.preferred_languages or [],
                "preferred_topics": profile.preferred_topics or [],
                "min_heat_threshold": profile.min_heat_threshold,
            }
        }

    state = await get_onboarding_status(db, user.id)
    return OnboardingStepResponse(
        status=state.status,
        completed_steps=state.completed_steps,
        available_steps=state.available_steps,
        can_complete=state.can_complete,
        step=step,
        payload=payload,
    )


@router.post("/onboarding/complete", response_model=OnboardingStatusResponse)
async def complete_onboarding_route(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    user, _ = auth

    try:
        state = await complete_onboarding(db, user.id)
    except CannotCompleteOnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OnboardingAlreadyCompletedError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return OnboardingStatusResponse(
        status=state.status,
        completed_steps=state.completed_steps,
        available_steps=state.available_steps,
        can_complete=state.can_complete,
    )


@router.post("/onboarding/skip", response_model=OnboardingStatusResponse)
async def skip_onboarding_route(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    user, _ = auth

    try:
        state = await skip_onboarding(db, user.id)
    except OnboardingAlreadyCompletedError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return OnboardingStatusResponse(
        status=state.status,
        completed_steps=state.completed_steps,
        available_steps=state.available_steps,
        can_complete=state.can_complete,
    )


@router.get("/preview-recommendations", response_model=PreviewRecommendationsResponse)
async def get_preview_recommendations_route(
    source: str | None = Query(
        default=None,
        description="Source vector to use: intent, resume, or github. If not provided, returns trending issues.",
    ),
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> PreviewRecommendationsResponse:
    user, _ = auth

    try:
        issues = await get_preview_recommendations(db, user.id, source)
    except InvalidSourceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PreviewRecommendationsResponse(
        source=source,
        issues=[
            PreviewIssueResponse(
                node_id=issue.node_id,
                title=issue.title,
                repo_name=issue.repo_name,
                primary_language=issue.primary_language,
                q_score=issue.q_score,
            )
            for issue in issues
        ],
    )

