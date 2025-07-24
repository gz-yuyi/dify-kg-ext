from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from dify_kg_ext.api import app
from dify_kg_ext.dataclasses import Answer, Knowledge


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
        patch("dify_kg_ext.api.index_document", new_callable=AsyncMock) as mock_index,
        patch(
            "dify_kg_ext.api.delete_documents", new_callable=AsyncMock
        ) as mock_delete,
        patch(
            "dify_kg_ext.api.bind_knowledge_to_library",
            new_callable=AsyncMock,
        ) as mock_bind,
        patch(
            "dify_kg_ext.api.unbind_knowledge_from_library",
            new_callable=AsyncMock,
        ) as mock_unbind,
    ):
        mock_index.return_value = "test_id_123"
        mock_delete.return_value = True
        mock_bind.return_value = True
        mock_unbind.return_value = True

        yield {
            "index_document": mock_index,
            "delete_documents": mock_delete,
            "bind_knowledge_to_library": mock_bind,
            "unbind_knowledge_from_library": mock_unbind,
        }


@pytest.fixture
def mock_ragflow_functions():
    """Mock RAGFlow-related functions used in document processing."""
    with (
        patch("dify_kg_ext.api.upload_and_parse_document") as mock_upload,
        patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk,
    ):
        # 设置默认返回值
        mock_upload.return_value = {
            "dataset_id": "ragflow_dataset_123",
            "document_id": "ragflow_doc_456",
            "chunks": ["Test chunk 1", "Test chunk 2"],
            "status": "completed",
        }

        mock_chunk.return_value = ["Direct text chunk 1", "Direct text chunk 2"]

        yield {
            "upload_and_parse_document": mock_upload,
            "chunk_text_directly": mock_chunk,
        }
