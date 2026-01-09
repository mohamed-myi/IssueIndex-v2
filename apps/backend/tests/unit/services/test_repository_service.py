"""Unit tests for repository_service."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.services.repository_service import (
    list_repositories,
    _escape_like_pattern,
    RepositoryItem,
    DEFAULT_LIMIT,
    MAX_LIMIT,
)


class TestEscapeLikePattern:
    """Tests for SQL LIKE pattern escaping."""

    def test_escapes_percent_wildcard(self):
        """Should escape % to prevent wildcard matching."""
        result = _escape_like_pattern("%")
        assert result == "\\%"

    def test_escapes_underscore_wildcard(self):
        """Should escape _ to prevent single-char wildcard matching."""
        result = _escape_like_pattern("_")
        assert result == "\\_"

    def test_escapes_backslash(self):
        """Should escape backslash first."""
        result = _escape_like_pattern("\\")
        assert result == "\\\\"

    def test_escapes_mixed_special_chars(self):
        """Should handle mixed special characters."""
        result = _escape_like_pattern("50% off_sale\\end")
        assert result == "50\\% off\\_sale\\\\end"

    def test_preserves_normal_text(self):
        """Should preserve normal text unchanged."""
        result = _escape_like_pattern("react")
        assert result == "react"

    def test_sql_injection_attempt(self):
        """Should treat SQL injection attempts as literal strings."""
        result = _escape_like_pattern("'; DROP TABLE--")
        assert result == "'; DROP TABLE--"


class TestListRepositories:
    """Tests for list_repositories function."""

    @pytest.mark.asyncio
    async def test_returns_repositories_list(self):
        """Should return list of repository items."""
        mock_db = AsyncMock()
        
        mock_row = MagicMock()
        mock_row.name = "facebook/react"
        mock_row.primary_language = "JavaScript"
        mock_row.issue_count = 1250
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        
        result = await list_repositories(mock_db)
        
        assert len(result) == 1
        assert isinstance(result[0], RepositoryItem)
        assert result[0].name == "facebook/react"
        assert result[0].issue_count == 1250

    @pytest.mark.asyncio
    async def test_filters_by_language(self):
        """Should filter by primary_language when provided."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, language="Python")
        
        # Verify SQL was called with language parameter
        call_args = mock_db.execute.call_args
        assert "language" in call_args[1]
        assert call_args[1]["language"] == "Python"

    @pytest.mark.asyncio
    async def test_language_case_insensitive(self):
        """Language filtering should be case-insensitive."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, language="typescript")
        
        # The query uses LOWER() for case-insensitive matching
        call_args = mock_db.execute.call_args
        sql_query = str(call_args[0][0])
        assert "LOWER" in sql_query

    @pytest.mark.asyncio
    async def test_filters_by_search_query(self):
        """Should filter by search query in repository name."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, search_query="react")
        
        call_args = mock_db.execute.call_args
        assert "search_pattern" in call_args[1]
        assert "%react%" in call_args[1]["search_pattern"]

    @pytest.mark.asyncio
    async def test_escapes_wildcard_in_search(self):
        """Should escape SQL wildcards in search query."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, search_query="%")
        
        call_args = mock_db.execute.call_args
        # The % should be escaped
        assert "%\\%%" in call_args[1]["search_pattern"]

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self):
        """Should respect limit parameter."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, limit=25)
        
        call_args = mock_db.execute.call_args
        assert call_args[1]["limit"] == 25

    @pytest.mark.asyncio
    async def test_clamps_limit_to_max(self):
        """Should clamp limit to MAX_LIMIT."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, limit=500)
        
        call_args = mock_db.execute.call_args
        assert call_args[1]["limit"] == MAX_LIMIT

    @pytest.mark.asyncio
    async def test_handles_negative_limit(self):
        """Should handle negative limit by using default."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, limit=-5)
        
        call_args = mock_db.execute.call_args
        assert call_args[1]["limit"] == DEFAULT_LIMIT

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_repos(self):
        """Should return empty list when no repositories found."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        result = await list_repositories(mock_db)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_null_primary_language(self):
        """Should handle repositories with null primary_language."""
        mock_db = AsyncMock()
        
        mock_row = MagicMock()
        mock_row.name = "owner/repo"
        mock_row.primary_language = None
        mock_row.issue_count = 10
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        
        result = await list_repositories(mock_db)
        
        assert len(result) == 1
        assert result[0].primary_language is None

    @pytest.mark.asyncio
    async def test_combines_language_and_search_filters(self):
        """Should combine both language and search filters."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        await list_repositories(mock_db, language="JavaScript", search_query="react")
        
        call_args = mock_db.execute.call_args
        assert "language" in call_args[1]
        assert "search_pattern" in call_args[1]


class TestConstants:
    """Tests for module constants."""

    def test_default_limit(self):
        """DEFAULT_LIMIT should be reasonable."""
        assert DEFAULT_LIMIT == 50

    def test_max_limit(self):
        """MAX_LIMIT should be reasonable."""
        assert MAX_LIMIT == 100
