import os
import threading
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

_init_lock = threading.RLock()
_env_loaded = False
_engine = None
_session_factory = None


def _load_env_once() -> None:
    global _env_loaded
    if _env_loaded:
        return

    with _init_lock:
        if _env_loaded:
            return
        try:
            load_dotenv(os.path.join(project_root, ".env.local"))
        except PermissionError:
            pass
        load_dotenv(os.path.join(project_root, ".env"))
        _env_loaded = True


def _database_url() -> str:
    _load_env_once()
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://")
    return database_url


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    with _init_lock:
        if _engine is None:
            _engine = create_async_engine(
                _database_url(),
                echo=False,
                pool_pre_ping=True,
                connect_args={
                    "prepared_statement_cache_size": 0,
                    "statement_cache_size": 0,
                },
            )
    return _engine


def get_async_session_factory():
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    with _init_lock:
        if _session_factory is None:
            _session_factory = sessionmaker(
                get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
            )
    return _session_factory


class _LazySessionFactory:
    def __call__(self, *args, **kwargs):
        return get_async_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(get_async_session_factory(), name)


class _LazyEngineProxy:
    def __getattr__(self, name: str):
        return getattr(get_engine(), name)

    def __repr__(self) -> str:
        return repr(get_engine())


engine = _LazyEngineProxy()
async_session_factory = _LazySessionFactory()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def reset_session_state_for_testing() -> None:
    global _env_loaded, _engine, _session_factory
    _env_loaded = False
    _engine = None
    _session_factory = None
