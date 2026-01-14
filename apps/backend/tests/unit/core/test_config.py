"""Unit tests for Settings configuration class"""

import os
from unittest.mock import patch

import pytest

from src.core.config import Settings, get_settings


class TestSettingsDefaults:
    """Tests verifying default values for performance settings"""

    def test_gatherer_concurrency_default(self):
        # Arrange
        settings = Settings()

        # Act & Assert
        assert settings.gatherer_concurrency == 10

    def test_max_issues_per_repo_default(self):
        # Arrange
        settings = Settings()

        # Act & Assert
        assert settings.max_issues_per_repo == 200


class TestSettingsEnvironmentOverride:
    """Tests verifying environment variable overrides work"""

    def test_gatherer_concurrency_override(self):
        # Arrange
        with patch.dict(os.environ, {"GATHERER_CONCURRENCY": "25"}):
            # Act
            settings = Settings()

            # Assert
            assert settings.gatherer_concurrency == 25

    def test_max_issues_per_repo_override(self):
        # Arrange
        with patch.dict(os.environ, {"MAX_ISSUES_PER_REPO": "500"}):
            # Act
            settings = Settings()

            # Assert
            assert settings.max_issues_per_repo == 500

    def test_zero_max_issues_disables_cap(self):
        # Arrange - zero value should be valid to disable capping
        with patch.dict(os.environ, {"MAX_ISSUES_PER_REPO": "0"}):
            # Act
            settings = Settings()

            # Assert
            assert settings.max_issues_per_repo == 0


class TestGetSettings:
    """Tests for the cached get_settings function"""

    def test_get_settings_returns_settings_instance(self):
        # Arrange & Act
        # Clear cache to ensure fresh instance
        get_settings.cache_clear()
        settings = get_settings()

        # Assert
        assert isinstance(settings, Settings)
        assert settings.gatherer_concurrency == 10
        assert settings.max_issues_per_repo == 200

    def test_get_settings_is_cached(self):
        # Arrange
        get_settings.cache_clear()

        # Act
        settings1 = get_settings()
        settings2 = get_settings()

        # Assert - should return same cached instance
        assert settings1 is settings2
