"""SQL builders for hybrid search stages."""

from textwrap import dedent, indent

from gim_backend.services.search_models import SearchFilters

RRF_K: int = 60

# Maximum candidates from each retrieval path, increased for better recall
CANDIDATE_LIMIT: int = 500


def _build_stage1_score_columns_sql(row_alias: str = "fused") -> str:
    """
    Shared Stage-1 freshness and final-score column expressions.

    This keeps the ranking math defined in one place for both the hybrid and
    BM25-only retrieval branches.
    """
    score_columns_sql = dedent(
        f"""
        GREATEST(
            :freshness_floor,
            POWER(
                0.5,
                (
                    EXTRACT(EPOCH FROM (NOW() - GREATEST({row_alias}.ingested_at, {row_alias}.github_created_at))) / 86400.0
                ) / NULLIF(:freshness_half_life_days, 0)
            )
        ) AS freshness,
        (
            {row_alias}.rrf_score +
            (:freshness_weight * GREATEST(
                :freshness_floor,
                POWER(
                    0.5,
                    (
                        EXTRACT(EPOCH FROM (NOW() - GREATEST({row_alias}.ingested_at, {row_alias}.github_created_at))) / 86400.0
                    ) / NULLIF(:freshness_half_life_days, 0)
                )
            ))
        ) AS final_score
        """
    ).strip()
    return indent(score_columns_sql, " " * 16)


def _build_stage1_sql(filters: SearchFilters, use_vector_path: bool) -> str:
    """
    Builds Stage 1 SQL: candidate retrieval without filters in CTEs,
    RRF fusion, then post-filter application.

    Key design decisions:
        No filters in CTEs: Prevents recall gaps with selective filters
        Post-fusion filtering: Applied in final WHERE clause
        Tie-breaking: q_score DESC for deterministic ordering
        COUNT(*) OVER(): Accurate total without separate query
    """

    # Post-fusion filter conditions
    filter_conditions = []
    if filters.languages:
        filter_conditions.append("r.primary_language = ANY(:langs)")
    if filters.labels:
        filter_conditions.append("fused.labels && :labels")
    if filters.repos:
        filter_conditions.append("r.full_name = ANY(:repos)")

    post_filter_where = ""
    if filter_conditions:
        post_filter_where = "WHERE " + " AND ".join(filter_conditions)

    if use_vector_path:
        sql = f"""
        WITH vector_results AS (
            SELECT
                i.node_id,
                i.labels,
                i.repo_id,
                i.q_score,
                i.github_created_at,
                i.ingested_at,
                ROW_NUMBER() OVER (ORDER BY i.embedding <=> CAST(:query_vec AS vector)) AS v_rank
            FROM ingestion.issue i
            WHERE i.embedding IS NOT NULL AND i.state = 'open'
            ORDER BY i.embedding <=> CAST(:query_vec AS vector)
            LIMIT :candidate_limit
        ),
        bm25_results AS (
            SELECT
                i.node_id,
                i.labels,
                i.repo_id,
                i.q_score,
                i.github_created_at,
                i.ingested_at,
                ROW_NUMBER() OVER (
                    ORDER BY ts_rank(i.search_vector, plainto_tsquery('english', :query_text)) DESC
                ) AS b_rank
            FROM ingestion.issue i
            WHERE i.search_vector @@ plainto_tsquery('english', :query_text) AND i.state = 'open'
            ORDER BY ts_rank(i.search_vector, plainto_tsquery('english', :query_text)) DESC
            LIMIT :candidate_limit
        ),
        vector_meta AS (
            SELECT COUNT(*) AS vector_candidate_count FROM vector_results
        ),
        bm25_meta AS (
            SELECT COUNT(*) AS bm25_candidate_count FROM bm25_results
        ),
        fused AS (
            SELECT
                COALESCE(v.node_id, b.node_id) AS node_id,
                COALESCE(v.labels, b.labels) AS labels,
                COALESCE(v.repo_id, b.repo_id) AS repo_id,
                COALESCE(v.q_score, b.q_score) AS q_score,
                COALESCE(v.github_created_at, b.github_created_at) AS github_created_at,
                COALESCE(v.ingested_at, b.ingested_at) AS ingested_at,
                COALESCE(1.0 / ({RRF_K} + v.v_rank), 0) +
                COALESCE(1.0 / ({RRF_K} + b.b_rank), 0) AS rrf_score
            FROM vector_results v
            FULL OUTER JOIN bm25_results b ON v.node_id = b.node_id
        ),
        filtered AS (
            SELECT
                fused.node_id,
                fused.rrf_score,
                fused.q_score,
{_build_stage1_score_columns_sql("fused")}
            FROM fused
            JOIN ingestion.repository r ON fused.repo_id = r.node_id
            {post_filter_where}
        )
        SELECT
            node_id,
            rrf_score,
            COUNT(*) OVER() AS total_count,
            (SELECT vector_candidate_count >= :candidate_limit FROM vector_meta) AS vector_capped,
            (SELECT bm25_candidate_count >= :candidate_limit FROM bm25_meta) AS bm25_capped
        FROM filtered
        ORDER BY final_score DESC, q_score DESC, node_id ASC
        """
    else:
        sql = f"""
        WITH bm25_results AS (
            SELECT
                i.node_id,
                i.labels,
                i.repo_id,
                i.q_score,
                i.github_created_at,
                i.ingested_at,
                ROW_NUMBER() OVER (
                    ORDER BY ts_rank(i.search_vector, plainto_tsquery('english', :query_text)) DESC
                ) AS b_rank
            FROM ingestion.issue i
            WHERE i.search_vector @@ plainto_tsquery('english', :query_text) AND i.state = 'open'
            ORDER BY ts_rank(i.search_vector, plainto_tsquery('english', :query_text)) DESC
            LIMIT :candidate_limit
        ),
        bm25_meta AS (
            SELECT COUNT(*) AS bm25_candidate_count FROM bm25_results
        ),
        fused AS (
            SELECT
                node_id,
                labels,
                repo_id,
                q_score,
                github_created_at,
                ingested_at,
                1.0 / ({RRF_K} + b_rank) AS rrf_score
            FROM bm25_results
        ),
        filtered AS (
            SELECT
                fused.node_id,
                fused.rrf_score,
                fused.q_score,
{_build_stage1_score_columns_sql("fused")}
            FROM fused
            JOIN ingestion.repository r ON fused.repo_id = r.node_id
            {post_filter_where}
        )
        SELECT
            node_id,
            rrf_score,
            COUNT(*) OVER() AS total_count,
            FALSE AS vector_capped,
            (SELECT bm25_candidate_count >= :candidate_limit FROM bm25_meta) AS bm25_capped
        FROM filtered
        ORDER BY final_score DESC, q_score DESC, node_id ASC
        """

    return sql


__all__ = [
    "RRF_K",
    "CANDIDATE_LIMIT",
    "_build_stage1_sql",
    "_build_stage1_score_columns_sql",
]
