import os
from unittest.mock import patch

import aresponses
import pytest

from dify_kg_ext.adapters import RerankResult
from dify_kg_ext.adapters.xinference import embedding, rerank


@pytest.fixture
def mock_xinference_host():
    with (
        patch.dict(os.environ, {"XINFERENCE_HOST": "http://test-host"}),
        patch("dify_kg_ext.adapters.xinference.BASE_URL", "http://test-host"),
    ):
        yield


@pytest.mark.asyncio
async def test_embedding(mock_xinference_host):
    test_input = "test text"
    expected_embedding = [0.1, 0.2, 0.3]

    async with aresponses.ResponsesMockServer() as arsps:
        arsps.add(
            "test-host",
            "/v1/embeddings",
            "post",
            aresponses.Response(
                status=200,
                headers={"Content-Type": "application/json"},
                body='{"data": [{"embedding": [0.1, 0.2, 0.3]}]}',
            ),
        )

        result = await embedding(test_input)
        assert result == expected_embedding


@pytest.mark.asyncio
async def test_rerank(mock_xinference_host):
    test_documents = ["doc1", "doc2", "doc3"]
    test_query = "test query"

    async with aresponses.ResponsesMockServer() as arsps:
        arsps.add(
            "test-host",
            "/v1/rerank",
            "post",
            aresponses.Response(
                status=200,
                headers={"Content-Type": "application/json"},
                body='{"results": [{"document": {"text": "doc3"}, "index": 2, "relevance_score": 0.9}, {"document": {"text": "doc1"}, "index": 0, "relevance_score": 0.7}, {"document": {"text": "doc2"}, "index": 1, "relevance_score": 0.5}]}',
            ),
        )

        results = await rerank(test_documents, test_query)
        assert len(results) == 3
        assert all(isinstance(r, RerankResult) for r in results)
        assert results[0].relevance_score == 0.9
        assert results[0].document.text == "doc3"
