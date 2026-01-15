"""
Pub/Sub message consumer for issue embedding.

Subscribes to issue topic, generates embeddings via local Nomic MoE,
and persists to database with idempotency checks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from .nomic_moe_embedder import NomicMoEEmbedder
from .survival_score import calculate_survival_score, days_since

logger = logging.getLogger(__name__)


class IssueEmbeddingConsumer:
    """
    Consumes issues from Pub/Sub and generates embeddings.

    Each message is:
    1. Deserialized from JSON
    2. Checked for idempotency via content_hash lookup
    3. Embedded using NomicMoEEmbedder (256-dim)
    4. Persisted to database with content_hash
    """

    def __init__(
        self,
        embedder: NomicMoEEmbedder,
        session_factory: Callable[[], AsyncSession],
    ):
        self._embedder = embedder
        self._session_factory = session_factory

    async def process_message(self, message_data: bytes) -> bool:
        """
        Process single Pub/Sub message; returns True if successful.

        Returns True for:
        - Successfully processed and persisted
        - Duplicate message (already processed)

        Returns False for:
        - Embedding generation failure
        - Database persistence failure
        - Invalid message format
        """
        try:
            data = json.loads(message_data.decode("utf-8"))
            content_hash = data.get("content_hash")
            node_id = data.get("node_id")

            if not node_id or not content_hash:
                logger.error("Message missing required fields: node_id or content_hash")
                return False

            # Idempotency check
            if await self._already_processed(node_id, content_hash):
                logger.debug(f"Skipping duplicate: {node_id} (hash: {content_hash[:8]}...)")
                return True

            # Generate embedding
            text_content = f"{data['title']}\n{data['body_text']}"
            embeddings = await self._embedder.embed_documents([text_content])

            if not embeddings or len(embeddings) == 0:
                logger.error(f"Embedding generation failed for {node_id}")
                return False

            # Persist to database
            await self._persist_issue(data, embeddings[0])

            logger.debug(
                f"Processed issue {node_id}",
                extra={"node_id": node_id, "content_hash": content_hash[:8]},
            )
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to process message: {e}")
            return False

    async def _already_processed(self, node_id: str, content_hash: str) -> bool:
        """
        Check if issue with same content hash already exists.

        We check for exact (node_id, content_hash) match to allow
        updates when content changes (different hash, same node_id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT 1 FROM ingestion.issue
                    WHERE node_id = :node_id AND content_hash = :content_hash
                """),
                {"node_id": node_id, "content_hash": content_hash},
            )
            return result.scalar() is not None

    async def _persist_issue(self, data: dict[str, Any], embedding: list[float]) -> None:
        """
        Persist issue with embedding to database.

        Uses UPSERT to handle both new issues and updates to existing ones.
        """
        # Parse github_created_at
        github_created_at = data.get("github_created_at")
        if isinstance(github_created_at, str):
            github_created_at = datetime.fromisoformat(github_created_at.replace("Z", "+00:00"))

        # Calculate survival score
        days_old = days_since(github_created_at)
        q_score = data.get("q_score", 0.0)
        survival = calculate_survival_score(q_score, days_old)

        # Extract q_components
        q_components = data.get("q_components", {})

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO ingestion.issue (
                        node_id, repo_id, has_code, has_template_headers,
                        tech_stack_weight, q_score, survival_score, title,
                        body_text, labels, embedding, content_hash, state,
                        github_created_at
                    )
                    VALUES (
                        :node_id, :repo_id, :has_code, :has_template_headers,
                        :tech_stack_weight, :q_score, :survival_score, :title,
                        :body_text, :labels, CAST(:embedding AS vector), :content_hash,
                        :state, :github_created_at
                    )
                    ON CONFLICT (node_id) DO UPDATE SET
                        repo_id = EXCLUDED.repo_id,
                        has_code = EXCLUDED.has_code,
                        has_template_headers = EXCLUDED.has_template_headers,
                        tech_stack_weight = EXCLUDED.tech_stack_weight,
                        q_score = EXCLUDED.q_score,
                        survival_score = EXCLUDED.survival_score,
                        title = EXCLUDED.title,
                        body_text = EXCLUDED.body_text,
                        labels = EXCLUDED.labels,
                        embedding = EXCLUDED.embedding,
                        content_hash = EXCLUDED.content_hash,
                        state = EXCLUDED.state,
                        github_created_at = EXCLUDED.github_created_at
                """),
                {
                    "node_id": data["node_id"],
                    "repo_id": data["repo_id"],
                    "has_code": q_components.get("has_code", False),
                    "has_template_headers": q_components.get("has_headers", False),
                    "tech_stack_weight": q_components.get("tech_weight", 0.0),
                    "q_score": q_score,
                    "survival_score": survival,
                    "title": data["title"],
                    "body_text": data["body_text"],
                    "labels": data.get("labels", []),
                    "embedding": str(embedding),
                    "content_hash": data["content_hash"],
                    "state": data.get("state", "open"),
                    "github_created_at": github_created_at,
                },
            )
            await session.commit()
