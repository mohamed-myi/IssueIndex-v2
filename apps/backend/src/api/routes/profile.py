"""Profile API routes. All endpoints require authentication."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.dependencies import get_db
from src.middleware.auth import require_auth
from src.services.profile_service import (
    get_or_create_profile,
    get_full_profile,
    delete_profile as delete_profile_service,
    create_intent as create_intent_service,
    put_intent as put_intent_service,
    get_intent as get_intent_service,
    update_intent as update_intent_service,
    delete_intent as delete_intent_service,
    get_preferences as get_preferences_service,
    update_preferences as update_preferences_service,
)
from src.core.errors import (
    InvalidTaxonomyValueError,
    IntentAlreadyExistsError,
    IntentNotFoundError,
)
from models.identity import User, Session


router = APIRouter()


class IntentCreateInput(BaseModel):
    languages: list[str] = Field(..., min_length=1, max_length=10)
    stack_areas: list[str] = Field(..., min_length=1)
    text: str = Field(..., min_length=10, max_length=2000)
    experience_level: Optional[str] = Field(default=None)


class IntentUpdateInput(BaseModel):
    languages: Optional[list[str]] = Field(default=None, min_length=1, max_length=10)
    stack_areas: Optional[list[str]] = Field(default=None, min_length=1)
    text: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    experience_level: Optional[str] = Field(default=None)


class PreferencesUpdateInput(BaseModel):
    preferred_languages: Optional[list[str]] = Field(default=None)
    preferred_topics: Optional[list[str]] = Field(default=None)
    min_heat_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class IntentDataOutput(BaseModel):
    languages: list[str]
    stack_areas: list[str]
    text: str
    experience_level: Optional[str]
    updated_at: Optional[str]


class IntentSourceOutput(BaseModel):
    populated: bool
    vector_status: Optional[str]
    data: Optional[IntentDataOutput]


class ResumeDataOutput(BaseModel):
    skills: list[str]
    job_titles: list[str]
    uploaded_at: Optional[str]


class ResumeSourceOutput(BaseModel):
    populated: bool
    vector_status: Optional[str]
    data: Optional[ResumeDataOutput]


class GitHubDataOutput(BaseModel):
    username: str
    languages: list[str]
    topics: list[str]
    fetched_at: Optional[str]


class GitHubSourceOutput(BaseModel):
    populated: bool
    vector_status: Optional[str]
    data: Optional[GitHubDataOutput]


class SourcesOutput(BaseModel):
    intent: IntentSourceOutput
    resume: ResumeSourceOutput
    github: GitHubSourceOutput


class PreferencesOutput(BaseModel):
    preferred_languages: list[str]
    preferred_topics: list[str]
    min_heat_threshold: float


class ProfileOutput(BaseModel):
    user_id: str
    optimization_percent: int
    combined_vector_status: Optional[str]
    is_calculating: bool
    onboarding_status: str
    updated_at: Optional[str]
    sources: SourcesOutput
    preferences: PreferencesOutput


class IntentOutput(BaseModel):
    languages: list[str]
    stack_areas: list[str]
    text: str
    experience_level: Optional[str]
    vector_status: Optional[str]
    updated_at: Optional[str]


class ProcessingStatusOutput(BaseModel):
    is_calculating: bool
    intent_status: str
    resume_status: str
    github_status: str
    intent_vector_status: Optional[str]
    resume_vector_status: Optional[str]
    github_vector_status: Optional[str]
    combined_vector_status: Optional[str]


@router.get("", response_model=ProfileOutput)
async def get_profile(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProfileOutput:
    user, _ = auth
    profile_data = await get_full_profile(db, user.id)
    
    sources = SourcesOutput(
        intent=IntentSourceOutput(
            populated=profile_data["sources"]["intent"]["populated"],
            vector_status=profile_data["sources"]["intent"]["vector_status"],
            data=IntentDataOutput(**profile_data["sources"]["intent"]["data"]) 
                if profile_data["sources"]["intent"]["data"] else None,
        ),
        resume=ResumeSourceOutput(
            populated=profile_data["sources"]["resume"]["populated"],
            vector_status=profile_data["sources"]["resume"]["vector_status"],
            data=ResumeDataOutput(**profile_data["sources"]["resume"]["data"])
                if profile_data["sources"]["resume"]["data"] else None,
        ),
        github=GitHubSourceOutput(
            populated=profile_data["sources"]["github"]["populated"],
            vector_status=profile_data["sources"]["github"]["vector_status"],
            data=GitHubDataOutput(**profile_data["sources"]["github"]["data"])
                if profile_data["sources"]["github"]["data"] else None,
        ),
    )
    
    return ProfileOutput(
        user_id=profile_data["user_id"],
        optimization_percent=profile_data["optimization_percent"],
        combined_vector_status=profile_data["combined_vector_status"],
        is_calculating=profile_data["is_calculating"],
        onboarding_status=profile_data["onboarding_status"],
        updated_at=profile_data["updated_at"],
        sources=sources,
        preferences=PreferencesOutput(**profile_data["preferences"]),
    )


@router.delete("")
async def delete_profile(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user, _ = auth
    was_deleted = await delete_profile_service(db, user.id)
    
    return {
        "deleted": was_deleted,
        "message": "Profile cleared" if was_deleted else "No profile data to clear",
    }


@router.post("/intent", response_model=IntentOutput, status_code=201)
async def create_intent(
    body: IntentCreateInput,
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> IntentOutput:
    user, _ = auth
    
    try:
        profile = await create_intent_service(
            db=db,
            user_id=user.id,
            languages=body.languages,
            stack_areas=body.stack_areas,
            text=body.text,
            experience_level=body.experience_level,
        )
    except InvalidTaxonomyValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntentAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    vector_status = "ready" if profile.intent_vector else None
    
    return IntentOutput(
        languages=profile.preferred_languages or [],
        stack_areas=profile.intent_stack_areas or [],
        text=profile.intent_text or "",
        experience_level=profile.intent_experience,
        vector_status=vector_status,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@router.get("/intent", response_model=IntentOutput)
async def get_intent(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> IntentOutput:
    user, _ = auth
    intent_data = await get_intent_service(db, user.id)
    
    if intent_data is None:
        raise HTTPException(status_code=404, detail="No intent data found")
    
    return IntentOutput(**intent_data)


@router.put("/intent", response_model=IntentOutput)
async def replace_intent(
    body: IntentCreateInput,
    response: Response,
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> IntentOutput:
    user, _ = auth

    try:
        profile, created = await put_intent_service(
            db=db,
            user_id=user.id,
            languages=body.languages,
            stack_areas=body.stack_areas,
            text=body.text,
            experience_level=body.experience_level,
        )
    except InvalidTaxonomyValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response.status_code = 201 if created else 200

    vector_status = "ready" if profile.intent_vector else None

    return IntentOutput(
        languages=profile.preferred_languages or [],
        stack_areas=profile.intent_stack_areas or [],
        text=profile.intent_text or "",
        experience_level=profile.intent_experience,
        vector_status=vector_status,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@router.patch("/intent", response_model=IntentOutput)
async def update_intent(
    body: IntentUpdateInput,
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> IntentOutput:
    user, _ = auth
    
    raw_body = body.model_dump(exclude_unset=True)
    experience_level_provided = "experience_level" in raw_body
    
    try:
        profile = await update_intent_service(
            db=db,
            user_id=user.id,
            languages=body.languages,
            stack_areas=body.stack_areas,
            text=body.text,
            experience_level=body.experience_level,
            _experience_level_provided=experience_level_provided,
        )
    except InvalidTaxonomyValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    vector_status = "ready" if profile.intent_vector else None
    
    return IntentOutput(
        languages=profile.preferred_languages or [],
        stack_areas=profile.intent_stack_areas or [],
        text=profile.intent_text or "",
        experience_level=profile.intent_experience,
        vector_status=vector_status,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@router.delete("/intent")
async def delete_intent(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user, _ = auth
    was_deleted = await delete_intent_service(db, user.id)
    
    if not was_deleted:
        raise HTTPException(status_code=404, detail="No intent data to delete")
    
    return {"deleted": True, "message": "Intent cleared"}


@router.get("/processing-status", response_model=ProcessingStatusOutput)
async def get_processing_status(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProcessingStatusOutput:
    user, _ = auth
    profile = await get_or_create_profile(db, user.id)

    def _status(data_present: bool, vector_present: bool) -> str:
        if vector_present:
            return "ready"
        if profile.is_calculating and data_present:
            return "processing"
        if data_present and not profile.is_calculating:
            return "failed"
        return "not_started"

    intent_data_present = profile.intent_text is not None
    resume_data_present = profile.resume_skills is not None
    github_data_present = profile.github_username is not None

    intent_vector_present = profile.intent_vector is not None
    resume_vector_present = profile.resume_vector is not None
    github_vector_present = profile.github_vector is not None
    combined_vector_present = profile.combined_vector is not None

    return ProcessingStatusOutput(
        is_calculating=profile.is_calculating,
        intent_status=_status(intent_data_present, intent_vector_present),
        resume_status=_status(resume_data_present, resume_vector_present),
        github_status=_status(github_data_present, github_vector_present),
        intent_vector_status="ready" if intent_vector_present else None,
        resume_vector_status="ready" if resume_vector_present else None,
        github_vector_status="ready" if github_vector_present else None,
        combined_vector_status="ready" if combined_vector_present else None,
    )


@router.get("/preferences", response_model=PreferencesOutput)
async def get_preferences(
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOutput:
    user, _ = auth
    prefs = await get_preferences_service(db, user.id)
    
    return PreferencesOutput(**prefs)


@router.patch("/preferences", response_model=PreferencesOutput)
async def update_preferences(
    body: PreferencesUpdateInput,
    auth: tuple[User, Session] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOutput:
    user, _ = auth
    
    try:
        profile = await update_preferences_service(
            db=db,
            user_id=user.id,
            preferred_languages=body.preferred_languages,
            preferred_topics=body.preferred_topics,
            min_heat_threshold=body.min_heat_threshold,
        )
    except InvalidTaxonomyValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return PreferencesOutput(
        preferred_languages=profile.preferred_languages or [],
        preferred_topics=profile.preferred_topics or [],
        min_heat_threshold=profile.min_heat_threshold,
    )
