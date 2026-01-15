"""Unit tests for Nomic MoE embedder with 256-dim Matryoshka truncation"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.ingestion.nomic_moe_embedder import (
    EMBEDDING_DIM,
    MODEL_NAME,
    NomicMoEEmbedder,
)


class TestEmbeddingDimConstants:
    """Verify embedding dimension constants"""

    def test_embedding_dim_is_256(self):
        """Matryoshka truncation should use 256 dimensions"""
        assert EMBEDDING_DIM == 256

    def test_model_name_is_v2_moe(self):
        """Model should be nomic-embed-text-v2-moe"""
        assert MODEL_NAME == "nomic-ai/nomic-embed-text-v2-moe"


class TestNomicMoEEmbedderInit:
    """Test embedder initialization"""

    def test_creates_with_default_workers(self):
        """Default max_workers should be 1"""
        embedder = NomicMoEEmbedder()
        assert embedder._executor._max_workers == 1
        embedder.close()

    def test_creates_with_custom_workers(self):
        """Should accept custom max_workers"""
        embedder = NomicMoEEmbedder(max_workers=2)
        assert embedder._executor._max_workers == 2
        embedder.close()

    def test_model_not_loaded_on_init(self):
        """Model should be lazy loaded, not on init"""
        embedder = NomicMoEEmbedder()
        assert embedder._model is None
        embedder.close()


class TestEmbedDocuments:
    """Test document embedding with search_document prefix"""

    @pytest.fixture
    def mock_model(self):
        """Mock SentenceTransformer model that returns 768-dim embeddings"""
        mock = MagicMock()
        # Return 768-dim embeddings that will be truncated to 256
        mock.encode.return_value = np.random.rand(1, 768).astype(np.float32)
        return mock

    @pytest.fixture
    def embedder_with_mock(self, mock_model):
        """Embedder with mocked model"""
        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_documents_returns_256_dim(self, embedder_with_mock, mock_model):
        """Document embeddings should be truncated to 256 dimensions"""
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        result = await embedder_with_mock.embed_documents(["Test document"])

        assert len(result) == 1
        assert len(result[0]) == 256

    @pytest.mark.asyncio
    async def test_document_prefix_applied(self, embedder_with_mock, mock_model):
        """Documents should have search_document prefix"""
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_documents(["Test document"])

        # Verify encode was called with prefixed text
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_document: Test document"]

    @pytest.mark.asyncio
    async def test_multiple_documents(self, embedder_with_mock, mock_model):
        """Should handle multiple documents in batch"""
        mock_model.encode.return_value = np.random.rand(3, 768).astype(np.float32)

        result = await embedder_with_mock.embed_documents([
            "First doc",
            "Second doc",
            "Third doc",
        ])

        assert len(result) == 3
        for emb in result:
            assert len(emb) == 256


class TestEmbedQueries:
    """Test query embedding with search_query prefix"""

    @pytest.fixture
    def mock_model(self):
        """Mock SentenceTransformer model"""
        mock = MagicMock()
        mock.encode.return_value = np.random.rand(1, 768).astype(np.float32)
        return mock

    @pytest.fixture
    def embedder_with_mock(self, mock_model):
        """Embedder with mocked model"""
        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_queries_returns_256_dim(self, embedder_with_mock, mock_model):
        """Query embeddings should be truncated to 256 dimensions"""
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        result = await embedder_with_mock.embed_queries(["Test query"])

        assert len(result) == 1
        assert len(result[0]) == 256

    @pytest.mark.asyncio
    async def test_query_prefix_applied(self, embedder_with_mock, mock_model):
        """Queries should have search_query prefix"""
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_queries(["Test query"])

        # Verify encode was called with prefixed text
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_query: Test query"]


class TestEmbeddingsNormalized:
    """Test that embeddings are properly normalized after truncation"""

    @pytest.fixture
    def embedder_with_mock(self):
        """Embedder with mocked model returning non-unit vectors"""
        mock_model = MagicMock()
        # Return non-normalized vectors
        raw_embedding = np.array([[2.0] * 768], dtype=np.float32)
        mock_model.encode.return_value = raw_embedding

        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embeddings_normalized_to_unit_vectors(self, embedder_with_mock):
        """Embeddings should be L2 normalized after truncation"""
        result = await embedder_with_mock.embed_documents(["Test"])

        # Calculate L2 norm
        embedding = np.array(result[0])
        norm = np.linalg.norm(embedding)

        # Should be unit vector (norm ~= 1.0)
        assert abs(norm - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_query_embeddings_also_normalized(self, embedder_with_mock):
        """Query embeddings should also be normalized"""
        result = await embedder_with_mock.embed_queries(["Test query"])

        embedding = np.array(result[0])
        norm = np.linalg.norm(embedding)

        assert abs(norm - 1.0) < 0.001


class TestEmptyInput:
    """Test edge case handling for empty inputs"""

    @pytest.fixture
    def embedder(self):
        """Embedder without mocked model"""
        embedder = NomicMoEEmbedder()
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_empty_documents_returns_empty(self, embedder):
        """Empty document list should return empty list"""
        result = await embedder.embed_documents([])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_queries_returns_empty(self, embedder):
        """Empty query list should return empty list"""
        result = await embedder.embed_queries([])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self, embedder):
        """Empty batch should return empty list"""
        result = await embedder.embed_batch([])
        assert result == []


class TestBatchSizeRespected:
    """Test batch size configuration"""

    def test_batch_size_is_25(self):
        """Default batch size should be 25"""
        embedder = NomicMoEEmbedder()
        assert embedder.BATCH_SIZE == 25
        embedder.close()


class TestConcurrentRequestsBounded:
    """Test that concurrent requests are bounded by thread pool"""

    def test_single_worker_limits_concurrency(self):
        """Single worker should process one batch at a time"""
        embedder = NomicMoEEmbedder(max_workers=1)
        assert embedder._executor._max_workers == 1
        embedder.close()

    def test_executor_created_with_specified_workers(self):
        """Executor should respect max_workers parameter"""
        embedder = NomicMoEEmbedder(max_workers=4)
        assert embedder._executor._max_workers == 4
        embedder.close()


class TestBackwardCompatibility:
    """Test backward compatibility with embed_batch method"""

    @pytest.fixture
    def embedder_with_mock(self):
        """Embedder with mocked model"""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_batch_uses_document_prefix(self, embedder_with_mock):
        """embed_batch should default to document embedding"""
        mock_model = embedder_with_mock._model
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_batch(["Test text"])

        # Should use document prefix
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_document: Test text"]

    @pytest.mark.asyncio
    async def test_embed_batch_returns_256_dim(self, embedder_with_mock):
        """embed_batch should return 256-dim embeddings"""
        result = await embedder_with_mock.embed_batch(["Test"])

        assert len(result) == 1
        assert len(result[0]) == 256


class TestTruncateAndNormalize:
    """Test the _truncate_and_normalize method directly"""

    def test_truncates_to_256_dims(self):
        """Should truncate 768-dim to 256-dim"""
        embedder = NomicMoEEmbedder()
        input_embedding = np.random.rand(1, 768).astype(np.float32)

        result = embedder._truncate_and_normalize(input_embedding)

        assert result.shape == (1, 256)
        embedder.close()

    def test_handles_batch_truncation(self):
        """Should handle batch of embeddings"""
        embedder = NomicMoEEmbedder()
        input_embeddings = np.random.rand(5, 768).astype(np.float32)

        result = embedder._truncate_and_normalize(input_embeddings)

        assert result.shape == (5, 256)
        embedder.close()

    def test_normalizes_after_truncation(self):
        """Should L2 normalize after truncation"""
        embedder = NomicMoEEmbedder()
        input_embedding = np.array([[1.0] * 768], dtype=np.float32)

        result = embedder._truncate_and_normalize(input_embedding)
        norm = np.linalg.norm(result[0])

        assert abs(norm - 1.0) < 0.001
        embedder.close()

    def test_handles_zero_vector(self):
        """Should handle zero vector without division error"""
        embedder = NomicMoEEmbedder()
        input_embedding = np.array([[0.0] * 768], dtype=np.float32)

        # Should not raise division by zero
        result = embedder._truncate_and_normalize(input_embedding)

        assert result.shape == (1, 256)
        embedder.close()


class TestModelLoading:
    """Test model lazy loading behavior"""

    def test_load_model_returns_model(self):
        """_load_model should return a model instance"""
        with patch("src.ingestion.nomic_moe_embedder.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            embedder = NomicMoEEmbedder()
            result = embedder._load_model()

            assert result == mock_model
            embedder.close()

    def test_load_model_caches_model(self):
        """_load_model should cache and reuse model instance"""
        with patch("src.ingestion.nomic_moe_embedder.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model

            embedder = NomicMoEEmbedder()
            result1 = embedder._load_model()
            result2 = embedder._load_model()

            # Should only create model once
            assert mock_st.call_count == 1
            assert result1 is result2
            embedder.close()

    def test_load_model_uses_correct_model_name(self):
        """_load_model should use nomic-embed-text-v2-moe"""
        with patch("src.ingestion.nomic_moe_embedder.SentenceTransformer") as mock_st:
            embedder = NomicMoEEmbedder()
            embedder._load_model()

            mock_st.assert_called_once_with(
                "nomic-ai/nomic-embed-text-v2-moe",
                trust_remote_code=True,
            )
            embedder.close()
