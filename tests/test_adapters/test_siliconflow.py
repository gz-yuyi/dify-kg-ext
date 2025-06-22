import os
from unittest.mock import patch

import aresponses
import pytest
from dify_kg_ext.adapters import RerankResult
from dify_kg_ext.adapters.siliconflow import embedding, rerank


@pytest.fixture
def mock_siliconflow_env():
    with patch.dict(os.environ, {"SILICONFLOW_TOKEN": "test-token"}):
        with patch("dify_kg_ext.adapters.siliconflow.BASE_URL", "http://test-host"):
            with patch(
                "dify_kg_ext.adapters.siliconflow.HEADERS",
                {
                    "Authorization": "Bearer test-token",
                    "Content-Type": "application/json",
                },
            ):
                yield


@pytest.mark.asyncio
async def test_embedding(mock_siliconflow_env):
    test_input = "test text"
    expected_embedding = [0.1, 0.2, 0.3]

    async with aresponses.ResponsesMockServer() as arsps:
        arsps.add(
            "test-host",
            "/embeddings",
            "post",
            aresponses.Response(
                status=200,
                headers={"Content-Type": "application/json"},
                body="""{
                    "model": "BAAI/bge-m3",
                    "data": [{"embedding": [0.1, 0.2, 0.3]}],
                    "usage": {"prompt_tokens": 5, "total_tokens": 5}
                }""",
            ),
        )

        result = await embedding(test_input)
        assert result == expected_embedding


@pytest.mark.asyncio
async def test_rerank(mock_siliconflow_env):
    test_documents = ["doc1", "doc2", "doc3"]
    test_query = "test query"

    async with aresponses.ResponsesMockServer() as arsps:
        arsps.add(
            "test-host",
            "/rerank",
            "post",
            aresponses.Response(
                status=200,
                headers={"Content-Type": "application/json"},
                body="""{
                    "id": "test-id-123",
                    "results": [
                        {"document": {"text": "doc3"}, "index": 2, "relevance_score": 0.9},
                        {"document": {"text": "doc1"}, "index": 0, "relevance_score": 0.7},
                        {"document": {"text": "doc2"}, "index": 1, "relevance_score": 0.5}
                    ],
                    "meta": {
                        "billed_units": {
                            "input_tokens": 10,
                            "output_tokens": 0,
                            "search_units": 0,
                            "classifications": 0
                        },
                        "tokens": {
                            "input_tokens": 10,
                            "output_tokens": 0
                        }
                    }
                }""",
            ),
        )

        results = await rerank(test_documents, test_query)
        assert len(results) == 3
        assert all(isinstance(r, RerankResult) for r in results)
        assert results[0].relevance_score == 0.9
        assert results[0].document.text == "doc3"