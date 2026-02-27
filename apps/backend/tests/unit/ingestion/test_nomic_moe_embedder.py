

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gim_backend.ingestion.nomic_moe_embedder import (
    EMBEDDING_DIM,
    MODEL_NAME,
    NomicMoEEmbedder,
)


class TestEmbeddingDimConstants:

    def test_embedding_dim_is_256(self):
        assert EMBEDDING_DIM == 256

    def test_model_name_is_v2_moe(self):
        assert MODEL_NAME == "nomic-ai/nomic-embed-text-v2-moe"


class TestNomicMoEEmbedderInit:

    def test_creates_with_default_workers(self):
        embedder = NomicMoEEmbedder()
        assert embedder._executor._max_workers == 1
        embedder.close()

    def test_creates_with_custom_workers(self):
        embedder = NomicMoEEmbedder(max_workers=2)
        assert embedder._executor._max_workers == 2
        embedder.close()

    def test_model_not_loaded_on_init(self):
        embedder = NomicMoEEmbedder()
        assert embedder._model is None
        embedder.close()


class TestEmbedDocuments:

    @pytest.fixture
    def mock_model(self):
        mock = MagicMock()

        mock.encode.return_value = np.random.rand(1, 768).astype(np.float32)
        return mock

    @pytest.fixture
    def embedder_with_mock(self, mock_model):
        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_documents_returns_256_dim(self, embedder_with_mock, mock_model):
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        result = await embedder_with_mock.embed_documents(["Test document"])

        assert len(result) == 1
        assert len(result[0]) == 256

    @pytest.mark.asyncio
    async def test_document_prefix_applied(self, embedder_with_mock, mock_model):
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_documents(["Test document"])


        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_document: Test document"]

    @pytest.mark.asyncio
    async def test_multiple_documents(self, embedder_with_mock, mock_model):
        mock_model.encode.return_value = np.random.rand(3, 768).astype(np.float32)

        result = await embedder_with_mock.embed_documents(
            [
                "First doc",
                "Second doc",
                "Third doc",
            ]
        )

        assert len(result) == 3
        for emb in result:
            assert len(emb) == 256


class TestEmbedQueries:

    @pytest.fixture
    def mock_model(self):
        mock = MagicMock()
        mock.encode.return_value = np.random.rand(1, 768).astype(np.float32)
        return mock

    @pytest.fixture
    def embedder_with_mock(self, mock_model):
        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_queries_returns_256_dim(self, embedder_with_mock, mock_model):
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        result = await embedder_with_mock.embed_queries(["Test query"])

        assert len(result) == 1
        assert len(result[0]) == 256

    @pytest.mark.asyncio
    async def test_query_prefix_applied(self, embedder_with_mock, mock_model):
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_queries(["Test query"])


        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_query: Test query"]


class TestEmbeddingsNormalized:

    @pytest.fixture
    def embedder_with_mock(self):
        mock_model = MagicMock()

        raw_embedding = np.array([[2.0] * 768], dtype=np.float32)
        mock_model.encode.return_value = raw_embedding

        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embeddings_normalized_to_unit_vectors(self, embedder_with_mock):
        result = await embedder_with_mock.embed_documents(["Test"])


        embedding = np.array(result[0])
        norm = np.linalg.norm(embedding)


        assert abs(norm - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_query_embeddings_also_normalized(self, embedder_with_mock):
        result = await embedder_with_mock.embed_queries(["Test query"])

        embedding = np.array(result[0])
        norm = np.linalg.norm(embedding)

        assert abs(norm - 1.0) < 0.001


class TestEmptyInput:

    @pytest.fixture
    def embedder(self):
        embedder = NomicMoEEmbedder()
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_empty_documents_returns_empty(self, embedder):
        result = await embedder.embed_documents([])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_queries_returns_empty(self, embedder):
        result = await embedder.embed_queries([])
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self, embedder):
        result = await embedder.embed_batch([])
        assert result == []


class TestBatchSizeRespected:

    def test_batch_size_is_25(self):
        embedder = NomicMoEEmbedder()
        assert embedder.BATCH_SIZE == 25
        embedder.close()


class TestConcurrentRequestsBounded:

    def test_single_worker_limits_concurrency(self):
        embedder = NomicMoEEmbedder(max_workers=1)
        assert embedder._executor._max_workers == 1
        embedder.close()

    def test_executor_created_with_specified_workers(self):
        embedder = NomicMoEEmbedder(max_workers=4)
        assert embedder._executor._max_workers == 4
        embedder.close()


class TestBackwardCompatibility:

    @pytest.fixture
    def embedder_with_mock(self):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        embedder = NomicMoEEmbedder()
        embedder._model = mock_model
        yield embedder
        embedder.close()

    @pytest.mark.asyncio
    async def test_embed_batch_uses_document_prefix(self, embedder_with_mock):
        mock_model = embedder_with_mock._model
        mock_model.encode.return_value = np.random.rand(1, 768).astype(np.float32)

        await embedder_with_mock.embed_batch(["Test text"])


        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["search_document: Test text"]

    @pytest.mark.asyncio
    async def test_embed_batch_returns_256_dim(self, embedder_with_mock):
        result = await embedder_with_mock.embed_batch(["Test"])

        assert len(result) == 1
        assert len(result[0]) == 256


class TestTruncateAndNormalize:

    def test_truncates_to_256_dims(self):
        embedder = NomicMoEEmbedder()
        input_embedding = np.random.rand(1, 768).astype(np.float32)

        result = embedder._truncate_and_normalize(input_embedding)

        assert result.shape == (1, 256)
        embedder.close()

    def test_handles_batch_truncation(self):
        embedder = NomicMoEEmbedder()
        input_embeddings = np.random.rand(5, 768).astype(np.float32)

        result = embedder._truncate_and_normalize(input_embeddings)

        assert result.shape == (5, 256)
        embedder.close()

    def test_normalizes_after_truncation(self):
        embedder = NomicMoEEmbedder()
        input_embedding = np.array([[1.0] * 768], dtype=np.float32)

        result = embedder._truncate_and_normalize(input_embedding)
        norm = np.linalg.norm(result[0])

        assert abs(norm - 1.0) < 0.001
        embedder.close()

    def test_handles_zero_vector(self):
        embedder = NomicMoEEmbedder()
        input_embedding = np.array([[0.0] * 768], dtype=np.float32)


        result = embedder._truncate_and_normalize(input_embedding)

        assert result.shape == (1, 256)
        embedder.close()


class TestMatryoshkaTruncationPublicApi:

    @pytest.mark.asyncio
    async def test_embed_documents_truncates_output(self):
        embedder = NomicMoEEmbedder()

        # Mock the synchronous encode method to return 768-dim vectors
        # This simulates the real model output before truncation
        with patch.object(embedder, "_encode_sync"):
            # The internal _encode_sync is called by public async methods.
            # However, in the real implementation, _encode_sync handles the truncation.
            # Wait, the CURRENT implementation has _encode_sync doing the truncation.
            # So if we mock _encode_sync, we mock the truncation too, which defeats the purpose.

            # We want to test that calling `embed_documents` results in 256-dim vectors.
            # But we can't load the real model (too heavy/slow/missing dependency).
            # We need to rely on the fact that `embed_documents` calls `_encode_sync`,
            # and `_encode_sync` calls `model.encode` then `_truncate_and_normalize`.

            # A better test here is to verify that `_truncate_and_normalize` is actually CALLED
            # with the output of the model, OR test `_encode_sync` logic directly by mocking ONLY the model.
            pass

        # Let's mock the internal _load_model to return a mock model that outputs 768 dims
        with patch.object(embedder, "_load_model") as mock_load:
            mock_model = MagicMock()
            # Model returns (batch, 768)
            mock_model.encode.return_value = np.random.rand(2, 768).astype(np.float32)
            mock_load.return_value = mock_model

            # Call the public sync method (which is what runs in the executor)
            # or simply call the async public API and await it (which runs the sync method)

            public_api_results = await embedder.embed_documents(["doc1", "doc2"])

            # Verify output dimensions
            assert len(public_api_results) == 2
            assert len(public_api_results[0]) == 256
            assert len(public_api_results[1]) == 256

            # Verify prefix was added (implementation detail, but important for correctness)
            mock_model.encode.assert_called_once()
            call_args = mock_model.encode.call_args[0][0]
            assert call_args[0].startswith("search_document: ")

            embedder.close()
