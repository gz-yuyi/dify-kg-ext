import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from dify_kg_ext.entrypoints.api import app
from dify_kg_ext.dataclasses import (
    Knowledge,
    Answer,
    KnowledgeDeleteRequest,
    KnowledgeBindBatchRequest,
    KnowledgeUnbindBatchRequest
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_knowledge():
    return Knowledge(
        segment_id="test_id_123",
        source="personal",
        knowledge_type="faq",
        question="How does this system work?",
        similar_questions=["How to use this system?"],
        answers=[
            Answer(
                content="This system works by processing knowledge entries.",
                channels=["channel_a"]
            )
        ],
        weight=5,
        document_id="doc_123",
        keywords=["system", "knowledge"],
        category_id="cat_001"
    )


@pytest_asyncio.fixture
async def mock_es_functions():
    with patch("dify_kg_ext.entrypoints.api.index_document", new_callable=AsyncMock) as mock_index, \
         patch("dify_kg_ext.entrypoints.api.delete_documents", new_callable=AsyncMock) as mock_delete, \
         patch("dify_kg_ext.entrypoints.api.bind_knowledge_to_library", new_callable=AsyncMock) as mock_bind, \
         patch("dify_kg_ext.entrypoints.api.unbind_knowledge_from_library", new_callable=AsyncMock) as mock_unbind:

        mock_index.return_value = "test_id_123"
        mock_delete.return_value = None
        mock_bind.return_value = {"success_count": 2, "failed_ids": []}
        mock_unbind.return_value = {"success_count": 1, "failed_ids": ["cat_002"]}

        yield {
            "index_document": mock_index,
            "delete_documents": mock_delete,
            "bind_knowledge_to_library": mock_bind,
            "unbind_knowledge_from_library": mock_unbind
        }


@pytest.mark.asyncio
async def test_update_knowledge(client, sample_knowledge, mock_es_functions):
    """Test the update_knowledge endpoint with valid data."""
    response = client.post("/knowledge/update", json=sample_knowledge.dict())
    
    assert response.status_code == 200
    assert response.json() == {"code": 200, "msg": "success"}
    mock_es_functions["index_document"].assert_called_once_with(sample_knowledge)


@pytest.mark.asyncio
async def test_delete_knowledge(client, mock_es_functions):
    """Test the delete_knowledge endpoint with valid segment IDs."""
    delete_request = KnowledgeDeleteRequest(segment_ids=["test_id_123", "test_id_456"])
    
    response = client.post("/knowledge/delete", json=delete_request.dict())
    
    assert response.status_code == 200
    assert response.json() == {"code": 200, "msg": "success"}
    mock_es_functions["delete_documents"].assert_called_once_with(["test_id_123", "test_id_456"])


@pytest.mark.asyncio
async def test_bind_knowledge_batch(client, mock_es_functions):
    """Test the bind_knowledge_batch endpoint with valid data."""
    bind_request = KnowledgeBindBatchRequest(
        library_id="lib_001",
        category_ids=["cat_001", "cat_002"]
    )
    
    response = client.post("/knowledge/bind_batch", json=bind_request.dict())
    
    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "msg": "success",
        "data": {
            "success_count": 2,
            "failed_ids": []
        }
    }
    mock_es_functions["bind_knowledge_to_library"].assert_called_once_with(
        library_id="lib_001",
        category_ids=["cat_001", "cat_002"]
    )


@pytest.mark.asyncio
async def test_unbind_knowledge_batch(client, mock_es_functions):
    """Test the unbind_knowledge_batch endpoint with valid data."""
    unbind_request = KnowledgeUnbindBatchRequest(
        library_id="lib_001",
        category_ids=["cat_001", "cat_002"],
        delete_type="part"
    )
    
    response = client.post("/knowledge/unbind_batch", json=unbind_request.dict())
    
    assert response.status_code == 200
    mock_es_functions["unbind_knowledge_from_library"].assert_called_once_with(
        library_id="lib_001",
        category_ids=["cat_001", "cat_002"],
        delete_type="part"
    )


@pytest.mark.asyncio
async def test_update_knowledge_failure(client, sample_knowledge, mock_es_functions):
    """Test the update_knowledge endpoint when indexing fails."""
    mock_es_functions["index_document"].return_value = None
    
    # When the index operation fails, the API should raise an HTTPException
    response = client.post("/knowledge/update", json=sample_knowledge.dict())
    assert response.status_code == 500
    assert "Failed to index document" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_delete_knowledge_empty_ids(client):
    """Test the delete_knowledge endpoint with empty segment IDs."""
    delete_request = {"segment_ids": []}
    
    response = client.post("/knowledge/delete", json=delete_request)
    
    assert response.status_code == 422  # Validation error expected


@pytest.mark.asyncio
async def test_bind_knowledge_batch_empty_category_ids(client):
    """Test the bind_knowledge_batch endpoint with empty category IDs."""
    bind_request = {"library_id": "lib_001", "category_ids": []}
    
    response = client.post("/knowledge/bind_batch", json=bind_request)
    
    assert response.status_code == 422  # Validation error expected


@pytest.mark.asyncio
async def test_unbind_knowledge_batch_part_with_empty_category_ids(client, mock_es_functions):
    """Test the unbind_knowledge_batch endpoint with empty category IDs and delete_type='part'."""
    unbind_request = {
        "library_id": "lib_001",
        "category_ids": [],
        "delete_type": "part"
    }
    
    response = client.post("/knowledge/unbind_batch", json=unbind_request)
    
    # The API accepts empty category_ids even with delete_type="part"
    assert response.status_code == 200
    mock_es_functions["unbind_knowledge_from_library"].assert_called_once_with(
        library_id="lib_001",
        category_ids=[],
        delete_type="part"
    )


@pytest.mark.asyncio
async def test_unbind_knowledge_batch_all(client, mock_es_functions):
    """Test the unbind_knowledge_batch endpoint with delete_type='all'."""
    unbind_request = KnowledgeUnbindBatchRequest(
        library_id="lib_001",
        category_ids=[],
        delete_type="all"
    )
    
    response = client.post("/knowledge/unbind_batch", json=unbind_request.dict())
    
    assert response.status_code == 200
    mock_es_functions["unbind_knowledge_from_library"].assert_called_once_with(
        library_id="lib_001",
        category_ids=[],
        delete_type="all"
    )


@pytest.mark.asyncio
async def test_unbind_knowledge_batch_empty_library_id(client):
    """Test the unbind_knowledge_batch endpoint with empty library_id."""
    unbind_request = {
        "library_id": "",  # Empty library_id
        "category_ids": ["cat_001"],
        "delete_type": "part"
    }
    
    response = client.post("/knowledge/unbind_batch", json=unbind_request)
    
    assert response.status_code == 422  # Validation error expected


@pytest.mark.asyncio
async def test_unbind_knowledge_batch_invalid_delete_type(client):
    """Test the unbind_knowledge_batch endpoint with an invalid delete_type."""
    unbind_request = {
        "library_id": "lib_001",
        "category_ids": ["cat_001"],
        "delete_type": "invalid"  # Invalid value, should be 'all' or 'part'
    }
    
    response = client.post("/knowledge/unbind_batch", json=unbind_request)
    
    assert response.status_code == 422  # Validation error expected 