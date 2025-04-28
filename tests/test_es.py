import pytest
from unittest.mock import patch, AsyncMock

from dify_kg_ext.es import (
    index_document,
    delete_documents,
    bind_knowledge_to_library,
    unbind_knowledge_from_library,
    search_knowledge,
    VECTOR_INDEX,
    KNOWLEDGE_INDEX,
    BINDING_INDEX
)
from dify_kg_ext.dataclasses import Knowledge, Answer

@pytest.fixture
def mock_es_client():
    with patch('dify_kg_ext.es.es_client') as mock_client:
        # Configure mock to work with async calls
        mock_client.indices.exists = AsyncMock(return_value=True)
        mock_client.indices.create = AsyncMock(return_value={"acknowledged": True})
        mock_client.bulk = AsyncMock(return_value={"errors": False})
        mock_client.delete_by_query = AsyncMock(return_value={"deleted": 2})
        mock_client.search = AsyncMock()
        mock_client.get = AsyncMock()
        mock_client.index = AsyncMock(return_value={"_id": "test_id"})
        
        yield mock_client

@pytest.fixture
def sample_knowledge():
    return Knowledge(
        segment_id="segment_123",
        source="personal",
        knowledge_type="faq",
        question="Test question",
        similar_questions=["Similar question"],
        answers=[Answer(content="Test answer", channels=["channel_a"])],
        weight=5,
        document_id="doc_789",
        keywords=["test", "knowledge"],
        category_id="cat_456"
    )

@pytest.fixture
def mock_embedding():
    with patch('dify_kg_ext.es.embedding', new_callable=AsyncMock) as mock_embed:
        # Return a simple mock vector of appropriate dimension
        mock_embed.return_value = [0.1] * 1024
        yield mock_embed

@pytest.mark.asyncio
async def test_index_document(mock_es_client, mock_embedding, sample_knowledge):
    # Set up mock search response
    mock_es_client.search.return_value = {
        "hits": {
            "hits": [{"_id": "vec_1"}]
        }
    }
    
    # Call the function with sample knowledge
    result = await index_document(sample_knowledge)
    
    # Verify embedding was called twice (question & answer)
    assert mock_embedding.call_count == 2
    
    # Verify delete_by_query was called to clean old vectors
    mock_es_client.delete_by_query.assert_called_once()
    
    # Verify bulk was called with operations
    mock_es_client.bulk.assert_called_once()
    
    # Verify correct segment_id is returned
    assert result == sample_knowledge.segment_id

@pytest.mark.asyncio
async def test_delete_documents(mock_es_client):
    segment_ids = ["segment_123", "segment_456"]
    
    # Set up mock search response
    mock_es_client.search.return_value = {
        "hits": {
            "hits": [{"_id": "vec_1"}, {"_id": "vec_2"}]
        }
    }
    
    # Call the function
    await delete_documents(segment_ids)
    
    # Verify search was called to find associated vectors
    mock_es_client.search.assert_called_once()
    
    # Verify bulk delete was called
    mock_es_client.bulk.assert_called_once()

@pytest.mark.asyncio
async def test_bind_knowledge_to_library(mock_es_client):
    # Call the function
    result = await bind_knowledge_to_library(
        library_id="lib_123",
        category_ids=["cat_1", "cat_2"]
    )
    
    # Verify index was called with correct data
    called_with = mock_es_client.index.call_args[1]
    assert called_with["index"] == BINDING_INDEX
    assert called_with["document"]["library_id"] == "lib_123"
    assert called_with["document"]["category_id"] == ["cat_1", "cat_2"]
    
    # Verify function return type
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_unbind_knowledge_from_library(mock_es_client):
    # Set up mock response for delete_by_query
    mock_es_client.delete_by_query.return_value = {"deleted": 3}
    
    # Call the function
    result = await unbind_knowledge_from_library(
        library_id="lib_123",
        category_ids=["cat_1", "cat_2"],
        delete_type="all"
    )
    
    # Verify delete_by_query was called with correct query
    called_with = mock_es_client.delete_by_query.call_args[1]
    assert called_with["index"] == BINDING_INDEX
    assert called_with["query"]["term"]["library_id"] == "lib_123"
    
    # Verify correct result is returned
    assert result == {"success_count": 3, "failed_ids": []}

@pytest.mark.asyncio
async def test_search_knowledge(mock_es_client, mock_embedding):
    # Set up mock response for get operation
    mock_es_client.get.return_value = {
        "_source": {
            "category_id": ["cat_1", "cat_2"]
        }
    }
    
    # Set up mock response for knowledge search
    mock_es_client.search.side_effect = [
        # First search call (vector search)
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "segment_id": "segment_123"
                        }
                    }
                ]
            }
        },
        # Second search call (knowledge document fetch)
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "segment_id": "segment_123",
                            "source": "personal",
                            "knowledge_type": "faq",
                            "question": "Test question",
                            "similar_questions": ["Similar question"],
                            "answers": [
                                {"content": "Test answer", "channels": ["channel_a"]}
                            ],
                            "weight": 5,
                            "document_id": "doc_789",
                            "keywords": ["test", "knowledge"],
                            "category_id": "cat_456"
                        }
                    }
                ]
            }
        }
    ]
    
    # Call the function
    result = await search_knowledge(
        query="test query",
        library_id="lib_123",
        limit=10
    )
    
    # Verify embedding was called with query
    mock_embedding.assert_called_once_with("test query")
    
    # Verify get was called to fetch categories
    mock_es_client.get.assert_called_once()
    
    # Verify search was called twice
    assert mock_es_client.search.call_count == 2
    
    # Verify result structure
    assert "segments" in result
    assert len(result["segments"]) == 1
    assert result["segments"][0].segment_id == "segment_123" 