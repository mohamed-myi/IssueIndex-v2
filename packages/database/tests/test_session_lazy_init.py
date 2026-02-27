"""Tests for lazy engine/session factory initialization."""

from unittest.mock import MagicMock, patch

import gim_database.session as session_module


def test_get_async_session_factory_initializes_once():
    session_module.reset_session_state_for_testing()

    fake_engine = MagicMock(name="engine")
    fake_session_factory = MagicMock(name="session_factory")

    with (
        patch.object(
            session_module, "create_async_engine", return_value=fake_engine
        ) as create_engine,
        patch.object(
            session_module,
            "sessionmaker",
            return_value=fake_session_factory,
        ) as sessionmaker_mock,
        patch.object(session_module, "load_dotenv") as load_dotenv_mock,
        patch.object(
            session_module.os,
            "getenv",
            return_value="postgresql://user:pass@localhost/db",
        ),
    ):
        first = session_module.get_async_session_factory()
        second = session_module.get_async_session_factory()

    assert first is fake_session_factory
    assert second is fake_session_factory
    create_engine.assert_called_once()
    sessionmaker_mock.assert_called_once()
    assert load_dotenv_mock.call_count == 2


def test_async_session_factory_proxy_delegates_call():
    session_module.reset_session_state_for_testing()

    sentinel_session_ctx = object()
    fake_session_factory = MagicMock(return_value=sentinel_session_ctx)

    with (
        patch.object(session_module, "create_async_engine", return_value=MagicMock()),
        patch.object(
            session_module,
            "sessionmaker",
            return_value=fake_session_factory,
        ),
        patch.object(session_module, "load_dotenv"),
        patch.object(
            session_module.os,
            "getenv",
            return_value="postgresql://user:pass@localhost/db",
        ),
    ):
        result = session_module.async_session_factory()

    assert result is sentinel_session_ctx
    fake_session_factory.assert_called_once_with()
