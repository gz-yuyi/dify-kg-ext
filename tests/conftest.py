from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from dify_kg_ext.dataclasses import Answer, Knowledge
from dify_kg_ext.api import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Return a TestClient instance for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_knowledge():
    """Return a sample Knowledge instance for testing."""
    return Knowledge(
        segment_id="test_id_123",
        source="personal",
        knowledge_type="faq",
        question="How does this system work?",
        similar_questions=["How to use this system?"],
        answers=[
            Answer(
                content="This system works by processing knowledge entries.",
                channels=["channel_a"],
            )
        ],
        weight=5,
        document_id="doc_123",
        keywords=["system", "knowledge"],
        category_id="cat_001",
    )


@pytest_asyncio.fixture
async def mock_es_functions():
    """Mock all Elasticsearch-related functions used in the API endpoints."""
    with (
        patch(
            "dify_kg_ext.entrypoints.api.index_document", new_callable=AsyncMock
        ) as mock_index,
        patch(
            "dify_kg_ext.entrypoints.api.delete_documents", new_callable=AsyncMock
        ) as mock_delete,
        patch(
            "dify_kg_ext.entrypoints.api.bind_knowledge_to_library",
            new_callable=AsyncMock,
        ) as mock_bind,
        patch(
            "dify_kg_ext.entrypoints.api.unbind_knowledge_from_library",
            new_callable=AsyncMock,
        ) as mock_unbind,
    ):
        mock_index.return_value = "test_id_123"
        mock_delete.return_value = None
        mock_bind.return_value = {"success_count": 2, "failed_ids": []}
        mock_unbind.return_value = {"success_count": 1, "failed_ids": ["cat_002"]}

        yield {
            "index_document": mock_index,
            "delete_documents": mock_delete,
            "bind_knowledge_to_library": mock_bind,
            "unbind_knowledge_from_library": mock_unbind,
        }