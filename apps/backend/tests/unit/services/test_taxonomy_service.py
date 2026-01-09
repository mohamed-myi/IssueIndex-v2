"""
Unit tests for taxonomy service.
"""
import pytest

from src.services.taxonomy_service import (
    get_languages,
    get_stack_areas,
    StackAreaInfo,
)
from constants import PROFILE_LANGUAGES, STACK_AREAS


class TestGetLanguages:
    """Tests for get_languages function."""

    def test_returns_list(self):
        """get_languages returns a list."""
        result = get_languages()
        assert isinstance(result, list)

    def test_contains_expected_languages(self):
        """Result contains all PROFILE_LANGUAGES."""
        result = get_languages()
        assert result == list(PROFILE_LANGUAGES)

    def test_contains_python(self):
        """Python is in the language list."""
        result = get_languages()
        assert "Python" in result

    def test_contains_typescript(self):
        """TypeScript is in the language list."""
        result = get_languages()
        assert "TypeScript" in result

    def test_count_matches_source(self):
        """Count matches PROFILE_LANGUAGES."""
        result = get_languages()
        assert len(result) == len(PROFILE_LANGUAGES)


class TestGetStackAreas:
    """Tests for get_stack_areas function."""

    def test_returns_list(self):
        """get_stack_areas returns a list."""
        result = get_stack_areas()
        assert isinstance(result, list)

    def test_returns_stack_area_info_objects(self):
        """Each item is a StackAreaInfo."""
        result = get_stack_areas()
        for item in result:
            assert isinstance(item, StackAreaInfo)

    def test_count_matches_source(self):
        """Count matches STACK_AREAS."""
        result = get_stack_areas()
        assert len(result) == len(STACK_AREAS)

    def test_backend_exists(self):
        """Backend stack area exists."""
        result = get_stack_areas()
        ids = [a.id for a in result]
        assert "backend" in ids

    def test_frontend_exists(self):
        """Frontend stack area exists."""
        result = get_stack_areas()
        ids = [a.id for a in result]
        assert "frontend" in ids

    def test_has_labels(self):
        """Each area has a non-empty label."""
        result = get_stack_areas()
        for item in result:
            assert item.label
            assert len(item.label) > 0

    def test_has_descriptions(self):
        """Each area has a non-empty description."""
        result = get_stack_areas()
        for item in result:
            assert item.description
            assert len(item.description) > 0

    def test_label_is_title_case(self):
        """Labels are title case transformed."""
        result = get_stack_areas()
        backend = next(a for a in result if a.id == "backend")
        assert backend.label == "Backend"
        
        data_eng = next(a for a in result if a.id == "data_engineering")
        assert data_eng.label == "Data Engineering"

    def test_description_matches_source(self):
        """Descriptions match STACK_AREAS values."""
        result = get_stack_areas()
        for item in result:
            assert item.description == STACK_AREAS[item.id]
