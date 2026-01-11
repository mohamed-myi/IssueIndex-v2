"""
Service for parsing resumes and extracting profile data.
Implements a 4 stage pipeline; Parse via Docling, Extract via GLiNER, Normalize, Embed.

For async processing via Cloud Tasks:
  - initiate_resume_processing() validates and enqueues task; returns immediately
  - process_resume() is the synchronous version for testing or fallback
  - Worker calls parse_resume_to_markdown, extract_entities, normalize_entities directly
"""
import logging
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID

from models.profiles import UserProfile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.services.cloud_tasks_service import enqueue_resume_task
from src.services.onboarding_service import mark_onboarding_in_progress
from src.services.profile_embedding_service import calculate_combined_vector
from src.services.vector_generation import generate_resume_vector_with_retry

shared_src = Path(__file__).resolve().parent.parent.parent.parent.parent / "packages" / "shared" / "src"
if str(shared_src) not in sys.path:
    sys.path.insert(0, str(shared_src))

from constants import normalize_skill  # noqa: E402

logger = logging.getLogger(__name__)


from src.core.errors import FileTooLargeError, ResumeParseError, UnsupportedFormatError  # noqa: E402

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ENTITY_LABELS = ["Skill", "Tool", "Framework", "Programming Language", "Job Title"]

_gliner_model = None


def validate_file(filename: str, content_type: str | None, file_size: int) -> None:
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError("Please upload a PDF or DOCX file")

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        if ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFormatError("Please upload a PDF or DOCX file")

    if file_size > MAX_FILE_SIZE:
        raise FileTooLargeError("Resume must be under 5MB")


def _get_gliner_model():
    global _gliner_model

    if _gliner_model is None:
        from gliner import GLiNER
        logger.info("Loading GLiNER model for resume entity extraction")
        _gliner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")

    return _gliner_model


def parse_resume_to_markdown(file_bytes: bytes, filename: str) -> str:
    """Converts document to Markdown via Docling. File never touches disk."""
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    try:
        buf = BytesIO(file_bytes)
        source = DocumentStream(name=filename, stream=buf)
        converter = DocumentConverter()
        result = converter.convert(source)
        markdown = result.document.export_to_markdown()

        if not markdown or not markdown.strip():
            raise ResumeParseError("We couldn't read your resume. Try a different format?")

        logger.info(f"Parsed resume to {len(markdown)} chars of Markdown")
        return markdown

    except ResumeParseError:
        raise
    except Exception as e:
        logger.warning(f"Docling parse failed: {e}")
        raise ResumeParseError("We couldn't read your resume. Try a different format?")


def extract_entities(markdown_text: str) -> list[dict]:
    """Extracts named entities via GLiNER. Returns empty list on failure."""
    if not markdown_text or not markdown_text.strip():
        return []

    model = _get_gliner_model()

    try:
        entities = model.predict_entities(markdown_text, ENTITY_LABELS, threshold=0.5)
        logger.info(f"Extracted {len(entities)} entities from resume")
        return entities
    except Exception as e:
        logger.warning(f"GLiNER extraction failed: {e}")
        return []


def normalize_entities(raw_entities: list[dict]) -> tuple[list[str], list[str], dict]:
    """
    Maps raw entities to canonical forms. Unrecognized entities stored for taxonomy expansion.
    Returns (skills, job_titles, raw_data) where raw_data preserves original extraction.
    """
    skills_set: set[str] = set()
    job_titles_set: set[str] = set()
    unrecognized: list[str] = []

    for entity in raw_entities:
        raw_text = entity.get("text", "")
        if raw_text is None:
            continue
        text = raw_text.strip()
        label = entity.get("label", "")

        if not text:
            continue

        if label == "Job Title":
            job_titles_set.add(text)
            continue

        normalized = normalize_skill(text)
        if normalized:
            skills_set.add(normalized)
        else:
            unrecognized.append(text)
            skills_set.add(text)

    raw_data = {
        "entities": raw_entities,
        "unrecognized": unrecognized,
        "extracted_at": datetime.now(UTC).isoformat(),
    }

    return list(skills_set), list(job_titles_set), raw_data


async def generate_resume_vector(markdown_text: str) -> list[float] | None:
    """Generates 768 dim embedding from full Markdown text with retry support."""
    if not markdown_text or not markdown_text.strip():
        logger.warning("Cannot generate resume vector: no text content")
        return None

    logger.info(f"Generating resume vector for text length {len(markdown_text)}")
    vector = await generate_resume_vector_with_retry(markdown_text)

    if vector is None:
        logger.warning("Resume vector generation failed after retries")
        return None

    return vector


def check_minimal_data(skills_count: int) -> str | None:
    """Returns warning if fewer than 3 skills; threshold per PROFILE.md."""
    if skills_count < 3:
        return (
            "We couldn't find many skills in your resume. "
            "For better recommendations, consider adding manual input."
        )
    return None


async def _get_or_create_profile(
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


async def initiate_resume_processing(
    db: AsyncSession,
    user_id: UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> dict:
    """
    Validates file and enqueues Cloud Task for async processing.
    Returns immediately with job_id and status 'processing'.

    The actual parsing happens in the resume worker via Cloud Tasks.
    """
    validate_file(filename, content_type, len(file_bytes))

    profile = await _get_or_create_profile(db, user_id)

    await mark_onboarding_in_progress(db, profile)

    profile.is_calculating = True
    await db.commit()

    job_id = await enqueue_resume_task(
        user_id=user_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
    )

    logger.info(f"Resume processing initiated for user {user_id}, job_id {job_id}")

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Resume uploaded. Processing in background.",
    }


async def process_resume(
    db: AsyncSession,
    user_id: UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> dict:
    """
    Synchronous version: Orchestrates all 4 pipeline stages and updates profile.
    Used for testing or as fallback when Cloud Tasks is unavailable.
    """
    validate_file(filename, content_type, len(file_bytes))

    profile = await _get_or_create_profile(db, user_id)

    await mark_onboarding_in_progress(db, profile)

    markdown = parse_resume_to_markdown(file_bytes, filename)
    raw_entities = extract_entities(markdown)
    skills, job_titles, raw_data = normalize_entities(raw_entities)
    minimal_warning = check_minimal_data(len(skills))

    profile.resume_skills = skills if skills else []
    profile.resume_job_titles = job_titles if job_titles else []
    profile.resume_raw_entities = raw_data
    profile.resume_uploaded_at = datetime.now(UTC)
    profile.is_calculating = True
    await db.commit()

    try:
        logger.info(f"Generating resume vector for {user_id}")
        resume_vector = await generate_resume_vector(markdown)
        profile.resume_vector = resume_vector

        combined = await calculate_combined_vector(
            intent_vector=profile.intent_vector,
            resume_vector=resume_vector,
            github_vector=profile.github_vector,
        )
        profile.combined_vector = combined
        logger.info(f"Resume vector generated for {user_id}")
    finally:
        profile.is_calculating = False

    await db.commit()
    await db.refresh(profile)

    return {
        "status": "ready",
        "skills": profile.resume_skills or [],
        "job_titles": profile.resume_job_titles or [],
        "vector_status": "ready" if profile.resume_vector else None,
        "uploaded_at": profile.resume_uploaded_at.isoformat() if profile.resume_uploaded_at else None,
        "minimal_data_warning": minimal_warning,
    }


async def get_resume_data(
    db: AsyncSession,
    user_id: UUID,
) -> dict | None:
    profile = await _get_or_create_profile(db, user_id)

    if profile.resume_skills is None:
        return None

    return {
        "status": "ready",
        "skills": profile.resume_skills or [],
        "job_titles": profile.resume_job_titles or [],
        "vector_status": "ready" if profile.resume_vector else None,
        "uploaded_at": profile.resume_uploaded_at.isoformat() if profile.resume_uploaded_at else None,
    }


async def delete_resume(
    db: AsyncSession,
    user_id: UUID,
) -> bool:
    profile = await _get_or_create_profile(db, user_id)

    if profile.resume_skills is None:
        return False

    profile.is_calculating = True
    await db.commit()

    try:
        profile.resume_skills = None
        profile.resume_job_titles = None
        profile.resume_raw_entities = None
        profile.resume_uploaded_at = None
        profile.resume_vector = None

        logger.info(f"Recalculating combined vector after resume deletion for {user_id}")
        combined = await calculate_combined_vector(
            intent_vector=profile.intent_vector,
            resume_vector=None,
            github_vector=profile.github_vector,
        )
        profile.combined_vector = combined
    finally:
        profile.is_calculating = False

    await db.commit()
    await db.refresh(profile)
    return True


def reset_gliner_for_testing() -> None:
    global _gliner_model
    _gliner_model = None


__all__ = [
    "MAX_FILE_SIZE",
    "ALLOWED_EXTENSIONS",
    "ALLOWED_CONTENT_TYPES",
    "validate_file",
    "parse_resume_to_markdown",
    "extract_entities",
    "normalize_entities",
    "generate_resume_vector",
    "check_minimal_data",
    "initiate_resume_processing",
    "process_resume",
    "get_resume_data",
    "delete_resume",
    "reset_gliner_for_testing",
]

