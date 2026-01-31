from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    direct_database_url: str = ""

    fingerprint_secret: str = ""
    fernet_key: str = ""  # Token encryption key for linked_accounts

    github_client_id: str = ""
    github_client_secret: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    session_remember_me_days: int = 7
    session_default_hours: int = 24
    max_sessions_per_user: int = 5

    frontend_base_url: str = "http://localhost:3000"

    redis_url: str = ""

    embedding_mode: str = "nomic"  # "nomic" or "vertex"

    reco_flush_secret: str = ""
    reco_events_flush_batch_size: int = 1000

    feed_freshness_half_life_days: float = 7.0
    feed_freshness_weight: float = 0.25
    feed_freshness_floor: float = 0.2
    feed_debug_freshness: bool = False

    search_freshness_half_life_days: float = 7.0
    search_freshness_weight: float = 0.25
    search_freshness_floor: float = 0.2

    max_auth_requests_per_minute: int = 10
    rate_limit_window_seconds: int = 60

    git_token: str = ""

    # Cloud Tasks config
    gcp_project: str = ""
    gcp_region: str = "us-central1"
    cloud_tasks_queue: str = "profile-jobs"
    embed_worker_url: str = ""
    resume_worker_url: str = ""

    # Performance optimizations
    gatherer_concurrency: int = 10  # Max concurrent repo fetches
    max_issues_per_repo: int = 100  # Cap issues per repository (reduced for rate limits)

    # Embedder job config (two-phase pipeline)
    embedder_batch_size: int = 250  # Issues per embedder batch

    # Janitor config
    janitor_min_issues: int = 10000  # Only prune if table exceeds this count

    # Embedding config for local Nomic MoE model
    embedding_model: str = "nomic-embed-text-v2-moe"
    embedding_dim: int = 256  # Matryoshka truncation from 768 to 256
    embedding_batch_size: int = 25
    max_concurrent_embeddings: int = 4  # Prevent OOM on constrained instances

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

