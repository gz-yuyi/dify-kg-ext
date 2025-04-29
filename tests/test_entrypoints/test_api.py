from fastapi.testclient import TestClient
from unittest.mock import patch

from dify_kg_ext.entrypoints.api import app
from dify_kg_ext.dataclasses import (
    Knowledge,
    KnowledgeDeleteRequest,
    KnowledgeBindBatchRequest,
    KnowledgeUnbindBatchRequest,
    KnowledgeSearchRequest,
    Answer
)

client = TestClient(app)

def test_update_knowledge():
    with patch('dify_kg_ext.entrypoints.api.index_document') as mock_index:
        mock_index.return_value = "segment_123"
        
        knowledge = Knowledge(
            segment_id="segment_123",
            source="personal",
            knowledge_type="faq",
            question="Test Question",
            answers=[Answer(content="Test answer", channels=["channel_a"])],
            weight=5,
            category_id="cat_456"
        )
        
        response = client.post("/knowledge/update", json=knowledge.model_dump())
        
        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success"}
        mock_index.assert_called_once_with(knowledge)

def test_update_knowledge_failure():
    with patch('dify_kg_ext.entrypoints.api.index_document') as mock_index:
        mock_index.return_value = None
        
        knowledge = Knowledge(
            segment_id="segment_123",
            source="personal",
            knowledge_type="faq",
            question="Test Question",
            answers=[Answer(content="Test answer", channels=["channel_a"])],
            weight=5,
            category_id="cat_456"
        )
        
        response = client.post("/knowledge/update", json=knowledge.model_dump())
        
        assert response.status_code == 500
        assert "Failed to index document" in response.json()["detail"]

def test_delete_knowledge():
    with patch('dify_kg_ext.entrypoints.api.delete_documents') as mock_delete:
        mock_delete.return_value = None
        
        request = KnowledgeDeleteRequest(segment_ids=["segment_123", "segment_456"])
        
        response = client.post("/knowledge/delete", json=request.model_dump())
        
        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success"}
        mock_delete.assert_called_once_with(request.segment_ids)

def test_bind_knowledge_batch():
    with patch('dify_kg_ext.entrypoints.api.bind_knowledge_to_library') as mock_bind:
        mock_result = {"success_count": 5, "failed_ids": []}
        mock_bind.return_value = mock_result
        
        request = KnowledgeBindBatchRequest(
            library_id="lib_123",
            category_ids=["cat_1", "cat_2", "cat_3"]
        )
        
        response = client.post("/knowledge/bind_batch", json=request.model_dump())
        
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "msg": "success",
            "data": mock_result
        }
        mock_bind.assert_called_once_with(
            library_id=request.library_id,
            category_ids=request.category_ids
        )

def test_unbind_knowledge_batch():
    with patch('dify_kg_ext.entrypoints.api.unbind_knowledge_from_library') as mock_unbind:
        mock_result = {"success_count": 3, "failed_ids": []}
        mock_unbind.return_value = mock_result
        
        request = KnowledgeUnbindBatchRequest(
            library_id="lib_123",
            category_ids=["cat_1", "cat_2"],
            delete_type="all"
        )
        
        response = client.post("/knowledge/unbind_batch", json=request.model_dump())
        
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "msg": "success",
            "data": mock_result
        }
        mock_unbind.assert_called_once_with(
            library_id=request.library_id,
            category_ids=request.category_ids,
            delete_type=request.delete_type
        )

def test_search_knowledge():
    with patch('dify_kg_ext.entrypoints.api.search_knowledge') as mock_search:
        # The es.py implementation returns a dict with "segments" key
        mock_knowledge = Knowledge(
            segment_id="segment_123",
            source="personal",
            knowledge_type="faq",
            question="How to search?",
            similar_questions=["How to find?"],
            answers=[Answer(content="Test search answer", channels=["channel_a"])],
            weight=5,
            document_id="doc_789",
            keywords=["search", "find"],
            category_id="cat_456"
        )
        # Return dictionary format matching es.py implementation
        mock_search.return_value = {"segments": [mock_knowledge]}
        
        request = KnowledgeSearchRequest(
            query="search query",
            library_id="lib_123",
            limit=5
        )
        
        response = client.post("/knowledge/search", json=request.model_dump())
        
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 200
        assert result["msg"] == "success"
        assert "segments" in result["data"]
        assert len(result["data"]["segments"]) == 1
        mock_search.assert_called_once_with(
            query=request.query,
            library_id=request.library_id,
            limit=request.limit
        ) 