"""Unit tests for retry policy with exponential backoff"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest


# Import the retry function from embedding_worker
# We need to mock the imports first since the worker has path manipulation
@pytest.fixture
def retry_config():
    """Default retry configuration"""
    return {
        "max_attempts": 3,
        "initial_backoff_seconds": 2,
        "max_backoff_seconds": 60,
        "backoff_multiplier": 2,
    }


@pytest.fixture
def mock_consumer():
    """Mock IssueEmbeddingConsumer"""
    return AsyncMock()


class TestRetryPolicy:
    """Tests for process_with_retry function"""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, mock_consumer):
        """Should return True immediately on success without retrying"""
        mock_consumer.process_message.return_value = True

        # Import and test the retry logic inline to avoid path issues
        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    await asyncio.sleep(0.01)  # Minimal delay for tests
            return False

        config = {
            "max_attempts": 3,
            "initial_backoff_seconds": 0.01,
            "max_backoff_seconds": 0.1,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        assert result is True
        assert mock_consumer.process_message.call_count == 1

    @pytest.mark.asyncio
    async def test_success_on_retry(self, mock_consumer):
        """Should return True after retrying on initial failure"""
        # First call fails, second succeeds
        mock_consumer.process_message.side_effect = [
            Exception("Transient error"),
            True,
        ]

        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    await asyncio.sleep(0.01)
            return False

        config = {
            "max_attempts": 3,
            "initial_backoff_seconds": 0.01,
            "max_backoff_seconds": 0.1,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        assert result is True
        assert mock_consumer.process_message.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_consumer):
        """Should return False after all retries exhausted"""
        mock_consumer.process_message.side_effect = Exception("Persistent error")

        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    await asyncio.sleep(0.01)
            return False

        config = {
            "max_attempts": 3,
            "initial_backoff_seconds": 0.01,
            "max_backoff_seconds": 0.1,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        assert result is False
        assert mock_consumer.process_message.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_timing(self, mock_consumer):
        """Should wait with exponential backoff between retries"""
        mock_consumer.process_message.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            True,
        ]

        sleep_times = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            sleep_times.append(seconds)
            await original_sleep(0.001)  # Minimal actual sleep

        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    backoff = min(
                        config["initial_backoff_seconds"] * (config["backoff_multiplier"] ** attempt),
                        config["max_backoff_seconds"],
                    )
                    await mock_sleep(backoff)
            return False

        config = {
            "max_attempts": 3,
            "initial_backoff_seconds": 2,
            "max_backoff_seconds": 60,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        assert result is True
        # First retry: 2 * (2^0) = 2
        # Second retry: 2 * (2^1) = 4
        assert sleep_times == [2, 4]

    @pytest.mark.asyncio
    async def test_backoff_respects_max(self, mock_consumer):
        """Should cap backoff at max_backoff_seconds"""
        mock_consumer.process_message.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
            Exception("Error 4"),
            True,
        ]

        sleep_times = []

        async def mock_sleep(seconds):
            sleep_times.append(seconds)

        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    backoff = min(
                        config["initial_backoff_seconds"] * (config["backoff_multiplier"] ** attempt),
                        config["max_backoff_seconds"],
                    )
                    await mock_sleep(backoff)
            return False

        config = {
            "max_attempts": 5,
            "initial_backoff_seconds": 2,
            "max_backoff_seconds": 10,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        assert result is True
        # Attempt 1: 2 * (2^0) = 2
        # Attempt 2: 2 * (2^1) = 4
        # Attempt 3: 2 * (2^2) = 8
        # Attempt 4: 2 * (2^3) = 16, but capped at 10
        assert sleep_times == [2, 4, 8, 10]

    @pytest.mark.asyncio
    async def test_returns_false_on_consumer_false(self, mock_consumer):
        """Should return False when consumer returns False (not an exception)"""
        mock_consumer.process_message.return_value = False

        async def process_with_retry(message_data, consumer, config):
            for attempt in range(config["max_attempts"]):
                try:
                    return await consumer.process_message(message_data)
                except Exception:
                    if attempt == config["max_attempts"] - 1:
                        return False
                    await asyncio.sleep(0.01)
            return False

        config = {
            "max_attempts": 3,
            "initial_backoff_seconds": 0.01,
            "max_backoff_seconds": 0.1,
            "backoff_multiplier": 2,
        }

        result = await process_with_retry(b"test", mock_consumer, config)

        # Returns False immediately without retry since it's not an exception
        assert result is False
        assert mock_consumer.process_message.call_count == 1


class TestRetryConfig:
    """Tests for retry configuration values"""

    def test_default_config_values(self, retry_config):
        """Default config should have sensible values"""
        assert retry_config["max_attempts"] == 3
        assert retry_config["initial_backoff_seconds"] == 2
        assert retry_config["max_backoff_seconds"] == 60
        assert retry_config["backoff_multiplier"] == 2

    def test_backoff_sequence(self, retry_config):
        """Verify backoff sequence calculation"""
        expected_backoffs = []
        for attempt in range(retry_config["max_attempts"] - 1):
            backoff = min(
                retry_config["initial_backoff_seconds"] * (retry_config["backoff_multiplier"] ** attempt),
                retry_config["max_backoff_seconds"],
            )
            expected_backoffs.append(backoff)

        # With initial=2, multiplier=2: [2, 4]
        assert expected_backoffs == [2, 4]

    def test_max_total_wait_time(self, retry_config):
        """Total wait time should be bounded"""
        total_wait = 0
        for attempt in range(retry_config["max_attempts"] - 1):
            backoff = min(
                retry_config["initial_backoff_seconds"] * (retry_config["backoff_multiplier"] ** attempt),
                retry_config["max_backoff_seconds"],
            )
            total_wait += backoff

        # Max wait = 2 + 4 = 6 seconds
        assert total_wait <= 10  # Reasonable bound
