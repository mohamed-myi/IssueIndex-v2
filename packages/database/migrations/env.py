import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel
from dotenv import load_dotenv

from alembic import context
from pgvector.sqlalchemy import Vector

import gim_database.models  # noqa: F401

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
load_dotenv(os.path.join(project_root, ".env.local"))
load_dotenv(os.path.join(project_root, ".env"))


config = context.config

# Override sqlalchemy.url with DIRECT_DATABASE_URL for migrations
# Falls back to DATABASE_URL if DIRECT_DATABASE_URL is not set
database_url = os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL", "")
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
# Escape percent signs to prevent parsing issues
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _compare_type(
    context, inspected_column, metadata_column, inspected_type, metadata_type
):
    """Custom type comparator that ignores equivalent PostgreSQL types.

    SQLModel's AutoString and SQLAlchemy's Text/String both map to PostgreSQL TEXT
    or VARCHAR. Without this, Alembic reports a perpetual cosmetic diff for every
    string column that the model declares as ``str`` (AutoString) but the DB
    reflects as TEXT.
    """
    from sqlmodel.sql.sqltypes import AutoString  # noqa: F811
    import sqlalchemy.types as satypes

    # TEXT/VARCHAR/String and AutoString are equivalent in PostgreSQL
    is_inspected_text = isinstance(inspected_type, (satypes.Text, satypes.String))
    is_metadata_auto = isinstance(metadata_type, AutoString)
    if is_inspected_text and is_metadata_auto:
        return False

    is_inspected_auto = isinstance(inspected_type, AutoString)
    is_metadata_text = isinstance(metadata_type, (satypes.Text, satypes.String))
    if is_inspected_auto and is_metadata_text:
        return False

    # Fall back to default comparison
    return None


def include_object(obj, name, type_, reflected, compare_to):
    """Exclude database-managed objects from autogenerate comparison.

    search_vector: A GENERATED ALWAYS AS ... STORED tsvector column on ingestion.issue,
    created via raw SQL migrations. Not in the Python model but actively used by the
    search service for BM25 full-text ranking. Its GIN index is also excluded.

    public-schema FKs: When include_schemas=True, PostgreSQL reflects public-schema
    FK references without the 'public.' prefix, but our models declare schema="public"
    explicitly. This creates a permanent cosmetic diff (e.g. users.id vs public.users.id)
    that is functionally identical. We suppress these to keep alembic check clean.
    """
    # Exclude the search_vector generated column
    if type_ == "column" and name == "search_vector":
        return False
    # Exclude the GIN index on search_vector
    if type_ == "index" and name == "ix_issue_search_vector":
        return False
    if type_ == "foreign_key_constraint":
        table = getattr(obj, "parent", None)
        schema = getattr(table, "schema", None) if table is not None else None
        if schema is None or schema == "public":
            return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # Register pgvector type for schema reflection
    connection.dialect.ischema_names["vector"] = Vector

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=_compare_type,
        render_as_batch=True,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Disable prepared statement caching for PgBouncer compatibility
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
