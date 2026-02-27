
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Side-effect imports: register models with SQLAlchemy ORM mapper
import gim_database.models.identity  # noqa: F401
import gim_database.models.persistence  # noqa: F401
import gim_database.models.profiles  # noqa: F401
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.exec = AsyncMock()
    return db


@pytest.fixture
def mock_profile():
    profile = MagicMock()
    profile.user_id = uuid4()
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
    profile.updated_at = datetime.now(UTC)
    return profile


@pytest.fixture(autouse=True)
def patch_profile_side_effects():
    """Prevent slow embedding/retry work from leaking into CRUD unit tests."""
    with (
        patch(
            "gim_backend.services.profile_service.mark_onboarding_in_progress",
            new_callable=AsyncMock,
        ),
        patch(
            "gim_backend.services.profile_service.generate_intent_vector_with_retry",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "gim_backend.services.profile_service.calculate_combined_vector",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        yield


class TestValidation:
    """Taxonomy validation boundary tests."""

    def test_validate_languages_accepts_all_valid_options(self):
        from gim_backend.services.profile_service import validate_languages

        validate_languages(["Python", "TypeScript", "Go", "Rust", "Java"])

    def test_validate_languages_rejects_invalid_value(self):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, validate_languages

        with pytest.raises(InvalidTaxonomyValueError) as exc:
            validate_languages(["Python", "Cobol"])

        assert exc.value.field == "language"
        assert exc.value.invalid_value == "Cobol"

    def test_validate_languages_rejects_empty_string(self):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, validate_languages

        with pytest.raises(InvalidTaxonomyValueError):
            validate_languages([""])

    def test_validate_languages_case_sensitive(self):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, validate_languages

        with pytest.raises(InvalidTaxonomyValueError):
            validate_languages(["python"])

    def test_validate_stack_areas_accepts_all_valid_options(self):
        from gim_backend.services.profile_service import validate_stack_areas

        validate_stack_areas(["backend", "frontend", "data_engineering", "machine_learning"])

    def test_validate_stack_areas_rejects_invalid_value(self):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, validate_stack_areas

        with pytest.raises(InvalidTaxonomyValueError) as exc:
            validate_stack_areas(["backend", "hacking"])

        assert exc.value.field == "stack_area"
        assert exc.value.invalid_value == "hacking"

    def test_validate_experience_level_accepts_all_valid_options(self):
        from gim_backend.services.profile_service import validate_experience_level

        validate_experience_level("beginner")
        validate_experience_level("intermediate")
        validate_experience_level("advanced")
        validate_experience_level(None)

    def test_validate_experience_level_rejects_invalid_value(self):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, validate_experience_level

        with pytest.raises(InvalidTaxonomyValueError) as exc:
            validate_experience_level("expert")

        assert exc.value.field == "experience_level"


class TestCalculateOptimizationPercent:

    def test_no_sources_returns_zero(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        assert calculate_optimization_percent(mock_profile) == 0

    def test_intent_only_returns_50(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.intent_text = "I want to work on Python projects"
        assert calculate_optimization_percent(mock_profile) == 50

    def test_resume_only_returns_30(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.resume_skills = ["Python", "FastAPI"]
        assert calculate_optimization_percent(mock_profile) == 30

    def test_github_only_returns_20(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.github_username = "octocat"
        assert calculate_optimization_percent(mock_profile) == 20

    def test_intent_plus_resume_returns_80(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.intent_text = "I want to work on Python projects"
        mock_profile.resume_skills = ["Python", "FastAPI"]
        assert calculate_optimization_percent(mock_profile) == 80

    def test_intent_plus_github_returns_70(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.intent_text = "I want to work on Python projects"
        mock_profile.github_username = "octocat"
        assert calculate_optimization_percent(mock_profile) == 70

    def test_resume_plus_github_returns_50(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.resume_skills = ["Python"]
        mock_profile.github_username = "octocat"
        assert calculate_optimization_percent(mock_profile) == 50

    def test_all_sources_returns_100(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.intent_text = "I want to work on Python projects"
        mock_profile.resume_skills = ["Python", "FastAPI"]
        mock_profile.github_username = "octocat"
        assert calculate_optimization_percent(mock_profile) == 100

    def test_empty_list_does_not_count_as_populated(self, mock_profile):
        from gim_backend.services.profile_service import calculate_optimization_percent

        mock_profile.resume_skills = []
        assert calculate_optimization_percent(mock_profile) == 0


class TestGetOrCreateProfile:

    async def test_returns_existing_profile(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import get_or_create_profile

        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        result = await get_or_create_profile(mock_db, user_id)

        assert result == mock_profile
        mock_db.add.assert_not_called()

    async def test_creates_profile_with_correct_defaults(self, mock_db):
        from gim_backend.services.profile_service import get_or_create_profile

        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.exec.return_value = mock_result

        await get_or_create_profile(mock_db, user_id)

        mock_db.add.assert_called_once()
        added_profile = mock_db.add.call_args[0][0]
        assert added_profile.user_id == user_id
        assert added_profile.min_heat_threshold == 0.6
        assert added_profile.onboarding_status == "not_started"
        assert added_profile.is_calculating is False


class TestIntentCrud:

    async def test_create_intent_stores_languages_in_preferred_languages(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import create_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        await create_intent(
            db=mock_db,
            user_id=mock_profile.user_id,
            languages=["Python", "TypeScript"],
            stack_areas=["backend"],
            text="I want to contribute to async Python libraries",
        )

        assert mock_profile.preferred_languages == ["Python", "TypeScript"]

    async def test_create_intent_rejects_duplicate(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import IntentAlreadyExistsError, create_intent

        mock_profile.intent_text = "Existing intent"
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with pytest.raises(IntentAlreadyExistsError):
            await create_intent(
                db=mock_db,
                user_id=mock_profile.user_id,
                languages=["Python"],
                stack_areas=["backend"],
                text="New intent text",
            )

    async def test_create_intent_validates_before_storing(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, create_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with pytest.raises(InvalidTaxonomyValueError):
            await create_intent(
                db=mock_db,
                user_id=mock_profile.user_id,
                languages=["InvalidLang"],
                stack_areas=["backend"],
                text="Some intent text",
            )

        mock_db.commit.assert_not_called()

    async def test_get_intent_returns_none_when_empty(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import get_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        result = await get_intent(mock_db, mock_profile.user_id)
        assert result is None

    async def test_update_intent_preserves_unmodified_fields(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import update_intent

        mock_profile.intent_text = "Original text"
        mock_profile.preferred_languages = ["Python"]
        mock_profile.intent_stack_areas = ["backend"]
        mock_profile.intent_experience = "beginner"

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        await update_intent(
            db=mock_db,
            user_id=mock_profile.user_id,
            experience_level="advanced",
            _experience_level_provided=True,
        )

        assert mock_profile.intent_experience == "advanced"
        assert mock_profile.intent_text == "Original text"
        assert mock_profile.preferred_languages == ["Python"]

    async def test_update_intent_raises_when_no_intent(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import IntentNotFoundError, update_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with pytest.raises(IntentNotFoundError):
            await update_intent(db=mock_db, user_id=mock_profile.user_id, text="Updated")

    async def test_delete_intent_clears_preferred_languages(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import delete_intent

        mock_profile.intent_text = "Some intent"
        mock_profile.preferred_languages = ["Python"]

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        await delete_intent(mock_db, mock_profile.user_id)

        assert mock_profile.preferred_languages is None
        assert mock_profile.intent_text is None

    async def test_delete_intent_returns_false_when_empty(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import delete_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        result = await delete_intent(mock_db, mock_profile.user_id)
        assert result is False


class TestPutIntent:

    @pytest.mark.asyncio
    async def test_put_creates_when_missing(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import put_intent

        mock_profile.intent_text = None
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with (
            patch(
                "gim_backend.services.profile_service.mark_onboarding_in_progress",
                new_callable=AsyncMock,
            ),
            patch(
                "gim_backend.services.profile_service.generate_intent_vector_with_retry",
                new_callable=AsyncMock,
                return_value=[0.1] * 768,
            ),
            patch(
                "gim_backend.services.profile_service.calculate_combined_vector",
                new_callable=AsyncMock,
                return_value=[0.2] * 768,
            ),
        ):
            profile, created = await put_intent(
                db=mock_db,
                user_id=mock_profile.user_id,
                languages=["Python"],
                stack_areas=["backend"],
                text="I want to contribute to open source Python projects",
                experience_level=None,
            )

        assert created is True
        assert profile.preferred_languages == ["Python"]
        assert profile.intent_text is not None

    @pytest.mark.asyncio
    async def test_put_replaces_without_reembed_when_only_languages_change(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import put_intent

        mock_profile.intent_text = "Same text"
        mock_profile.intent_stack_areas = ["backend"]
        mock_profile.intent_experience = "beginner"
        mock_profile.intent_vector = [0.1] * 768
        mock_profile.combined_vector = [0.2] * 768

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with (
            patch(
                "gim_backend.services.profile_service.generate_intent_vector_with_retry",
                new_callable=AsyncMock,
            ) as mock_embed,
            patch(
                "gim_backend.services.profile_service.calculate_combined_vector",
                new_callable=AsyncMock,
            ) as mock_combined,
        ):
            profile, created = await put_intent(
                db=mock_db,
                user_id=mock_profile.user_id,
                languages=["Python", "TypeScript"],
                stack_areas=["backend"],
                text="Same text",
                experience_level=None,
            )

        assert created is False
        assert profile.preferred_languages == ["Python", "TypeScript"]
        assert profile.intent_experience is None
        mock_embed.assert_not_called()
        mock_combined.assert_not_called()

    @pytest.mark.asyncio
    async def test_put_replaces_and_reembeds_when_text_changes(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import put_intent

        mock_profile.intent_text = "Old text"
        mock_profile.intent_stack_areas = ["backend"]
        mock_profile.intent_vector = [0.1] * 768
        mock_profile.combined_vector = [0.2] * 768

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with (
            patch(
                "gim_backend.services.profile_service.generate_intent_vector_with_retry",
                new_callable=AsyncMock,
                return_value=[0.3] * 768,
            ) as mock_embed,
            patch(
                "gim_backend.services.profile_service.calculate_combined_vector",
                new_callable=AsyncMock,
                return_value=[0.4] * 768,
            ) as mock_combined,
        ):
            profile, created = await put_intent(
                db=mock_db,
                user_id=mock_profile.user_id,
                languages=["Python"],
                stack_areas=["backend"],
                text="New text",
                experience_level="intermediate",
            )

        assert created is False
        assert profile.intent_text == "New text"
        assert profile.intent_experience == "intermediate"
        mock_embed.assert_called_once()
        mock_combined.assert_called_once()


class TestPreferences:

    async def test_update_preferences_validates_languages(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import InvalidTaxonomyValueError, update_preferences

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with pytest.raises(InvalidTaxonomyValueError):
            await update_preferences(
                db=mock_db,
                user_id=mock_profile.user_id,
                preferred_languages=["InvalidLang"],
            )

    async def test_update_preferences_preserves_unmodified_fields(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import update_preferences

        mock_profile.preferred_languages = ["Python"]
        mock_profile.preferred_topics = ["web"]
        mock_profile.min_heat_threshold = 0.6

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        await update_preferences(db=mock_db, user_id=mock_profile.user_id, min_heat_threshold=0.8)

        assert mock_profile.min_heat_threshold == 0.8
        assert mock_profile.preferred_languages == ["Python"]


class TestDeleteProfile:

    async def test_delete_profile_resets_to_defaults(self, mock_db, mock_profile):
        from unittest.mock import patch

        from gim_backend.services.profile_service import delete_profile

        mock_profile.intent_text = "Some intent"
        mock_profile.resume_skills = ["Python"]
        mock_profile.github_username = "octocat"
        mock_profile.min_heat_threshold = 0.9

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with patch("gim_backend.services.profile_service.cancel_user_tasks", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = 0
            await delete_profile(mock_db, mock_profile.user_id)

        assert mock_profile.intent_text is None
        assert mock_profile.resume_skills is None
        assert mock_profile.github_username is None
        assert mock_profile.min_heat_threshold == 0.6
        assert mock_profile.onboarding_status == "not_started"

    async def test_delete_profile_returns_false_when_not_found(self, mock_db):
        from unittest.mock import patch

        from gim_backend.services.profile_service import delete_profile

        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.exec.return_value = mock_result

        with patch("gim_backend.services.profile_service.cancel_user_tasks", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = 0
            result = await delete_profile(mock_db, uuid4())

        assert result is False

    async def test_delete_profile_cancels_cloud_tasks(self, mock_db, mock_profile):
        from unittest.mock import patch

        from gim_backend.services.profile_service import delete_profile

        mock_profile.intent_text = "Some intent"
        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        with patch("gim_backend.services.profile_service.cancel_user_tasks", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = 2
            await delete_profile(mock_db, mock_profile.user_id)
            mock_cancel.assert_called_once_with(mock_profile.user_id)


class TestGetFullProfile:

    async def test_response_structure_matches_spec(self, mock_db, mock_profile):
        from gim_backend.services.profile_service import get_full_profile

        mock_profile.intent_text = "I want to work on Python"
        mock_profile.preferred_languages = ["Python"]
        mock_profile.intent_stack_areas = ["backend"]

        mock_result = MagicMock()
        mock_result.first.return_value = mock_profile
        mock_db.exec.return_value = mock_result

        result = await get_full_profile(mock_db, mock_profile.user_id)

        assert result.user_id is not None
        assert result.optimization_percent is not None
        assert result.sources is not None
        assert result.preferences is not None
        assert result.sources.intent.populated is True
        assert result.sources.resume.populated is False
        assert result.sources.github.populated is False
