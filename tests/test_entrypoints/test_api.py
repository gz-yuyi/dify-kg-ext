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

def test_retrieval_endpoint():
    with patch('dify_kg_ext.entrypoints.api.check_knowledge_exists') as mock_check, \
         patch('dify_kg_ext.entrypoints.api.retrieve_knowledge') as mock_retrieve:
        
        # 设置知识库存在并返回结果
        mock_check.return_value = True
        mock_records = {
            "records": [
                {
                    "content": "Sample content for retrieval",
                    "score": 0.85,
                    "title": "Sample Title",
                    "metadata": {
                        "document_id": "doc_123",
                        "category_id": "cat_456",
                        "knowledge_type": "faq"
                    }
                }
            ]
        }
        mock_retrieve.return_value = mock_records
        
        # 准备测试请求
        request_data = {
            "knowledge_id": "lib_123",
            "query": "test retrieval query",
            "retrieval_setting": {
                "top_k": 5,
                "score_threshold": 0.6
            }
        }
        
        # 添加授权头
        headers = {"Authorization": "Bearer your-api-key"}
        
        # 发送请求
        response = client.post("/retrieval", json=request_data, headers=headers)
        
        # 验证响应
        assert response.status_code == 200
        assert response.json() == mock_records
        
        # 验证函数调用
        mock_check.assert_called_once_with(request_data["knowledge_id"])
        mock_retrieve.assert_called_once_with(
            knowledge_id=request_data["knowledge_id"],
            query=request_data["query"],
            top_k=request_data["retrieval_setting"]["top_k"],
            score_threshold=request_data["retrieval_setting"]["score_threshold"],
            metadata_condition=None
        )

def test_retrieval_nonexistent_knowledge():
    with patch('dify_kg_ext.entrypoints.api.check_knowledge_exists') as mock_check:
        # 设置知识库不存在
        mock_check.return_value = False
        
        # 准备测试请求
        request_data = {
            "knowledge_id": "nonexistent_lib",
            "query": "test query",
            "retrieval_setting": {
                "top_k": 5,
                "score_threshold": 0.6
            }
        }
        
        # 添加授权头
        headers = {"Authorization": "Bearer your-api-key"}
        
        # 发送请求
        response = client.post("/retrieval", json=request_data, headers=headers)
        
        # 验证响应
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == 2001
        assert "knowledge does not exist" in response.json()["detail"]["error_msg"]

def test_retrieval_invalid_auth():
    # 没有授权头
    request_data = {
        "knowledge_id": "lib_123",
        "query": "test query",
        "retrieval_setting": {
            "top_k": 5,
            "score_threshold": 0.6
        }
    }
    
    response = client.post("/retrieval", json=request_data)
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == 1001
    
    # 错误格式的授权头
    headers = {"Authorization": "InvalidFormat"}
    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == 1001
    
    # 无效的API密钥
    headers = {"Authorization": "Bearer invalid-key"}
    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == 1002

def test_retrieval_with_metadata_condition():
    with patch('dify_kg_ext.entrypoints.api.check_knowledge_exists') as mock_check, \
         patch('dify_kg_ext.entrypoints.api.retrieve_knowledge') as mock_retrieve:
        
        # 设置知识库存在并返回结果
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}
        
        # 准备带元数据条件的测试请求
        request_data = {
            "knowledge_id": "lib_123",
            "query": "test query with metadata",
            "retrieval_setting": {
                "top_k": 5,
                "score_threshold": 0.6
            },
            "metadata_condition": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "name": ["category"],
                        "comparison_operator": "contains",
                        "value": "test"
                    }
                ]
            }
        }
        
        # 添加授权头
        headers = {"Authorization": "Bearer your-api-key"}
        
        # 发送请求
        response = client.post("/retrieval", json=request_data, headers=headers)
        
        # 验证响应
        assert response.status_code == 200
        
        # 验证元数据条件传递
        mock_retrieve.assert_called_once()
        _, kwargs = mock_retrieve.call_args
        assert "metadata_condition" in kwargs
        assert kwargs["metadata_condition"].logical_operator == "and"
        assert len(kwargs["metadata_condition"].conditions) == 1 