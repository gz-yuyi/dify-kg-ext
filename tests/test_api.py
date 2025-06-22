from unittest.mock import patch

from dify_kg_ext.dataclasses import (
    Answer,
    Knowledge,
    KnowledgeBindBatchRequest,
    KnowledgeDeleteRequest,
    KnowledgeSearchRequest,
    KnowledgeUnbindBatchRequest,
)
from dify_kg_ext.dataclasses.doc_parse import (
    AnalyzingDocumentRequest,
    UploadDocumentRequest,
)
from dify_kg_ext.api import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


def test_update_knowledge():
    with patch("dify_kg_ext.api.index_document") as mock_index:
        mock_index.return_value = "segment_123"

        knowledge = Knowledge(
            segment_id="segment_123",
            source="personal",
            knowledge_type="faq",
            question="Test Question",
            answers=[Answer(content="Test answer", channels=["channel_a"])],
            weight=5,
            category_id="cat_456",
        )

        response = client.post("/knowledge/update", json=knowledge.model_dump())

        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success"}
        mock_index.assert_called_once_with(knowledge)


def test_update_knowledge_failure():
    with patch("dify_kg_ext.api.index_document") as mock_index:
        mock_index.return_value = None

        knowledge = Knowledge(
            segment_id="segment_123",
            source="personal",
            knowledge_type="faq",
            question="Test Question",
            answers=[Answer(content="Test answer", channels=["channel_a"])],
            weight=5,
            category_id="cat_456",
        )

        response = client.post("/knowledge/update", json=knowledge.model_dump())

        assert response.status_code == 500
        result = response.json()
        # The API uses custom error format with error_code and error_msg
        assert result["error_code"] == 500
        assert "Failed to index document" in result["error_msg"]


def test_delete_knowledge():
    with patch("dify_kg_ext.api.delete_documents") as mock_delete:
        mock_delete.return_value = None

        request = KnowledgeDeleteRequest(segment_ids=["segment_123", "segment_456"])

        response = client.post("/knowledge/delete", json=request.model_dump())

        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success"}
        mock_delete.assert_called_once_with(request.segment_ids)


def test_bind_knowledge_batch():
    with patch("dify_kg_ext.api.bind_knowledge_to_library") as mock_bind:
        mock_result = {"success_count": 5, "failed_ids": []}
        mock_bind.return_value = mock_result

        request = KnowledgeBindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2", "cat_3"]
        )

        response = client.post("/knowledge/bind_batch", json=request.model_dump())

        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success", "data": mock_result}
        mock_bind.assert_called_once_with(
            library_id=request.library_id, category_ids=request.category_ids
        )


def test_unbind_knowledge_batch():
    with patch(
        "dify_kg_ext.api.unbind_knowledge_from_library"
    ) as mock_unbind:
        mock_result = {"success_count": 3, "failed_ids": []}
        mock_unbind.return_value = mock_result

        request = KnowledgeUnbindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2"], delete_type="all"
        )

        response = client.post("/knowledge/unbind_batch", json=request.model_dump())

        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success", "data": mock_result}
        mock_unbind.assert_called_once_with(
            library_id=request.library_id,
            category_ids=request.category_ids,
            delete_type=request.delete_type,
        )


def test_search_knowledge():
    with patch("dify_kg_ext.api.search_knowledge") as mock_search:
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
            category_id="cat_456",
        )
        # Return dictionary format matching es.py implementation
        mock_search.return_value = {"segments": [mock_knowledge]}

        request = KnowledgeSearchRequest(
            query="search query", library_id="lib_123", limit=5
        )

        response = client.post("/knowledge/search", json=request.model_dump())

        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 200
        assert result["msg"] == "success"
        assert "segments" in result["data"]
        assert len(result["data"]["segments"]) == 1
        mock_search.assert_called_once_with(
            query=request.query, library_id=request.library_id, limit=request.limit
        )


# ==================== 新增测试用例 ====================


# 系统功能测试
def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "healthy"
    assert result["service"] == "knowledge-database-api"
    assert "features" in result
    assert "knowledge-management" in result["features"]
    assert "dify-external-knowledge-api" in result["features"]


def test_root_endpoint():
    """测试根路径信息端点"""
    response = client.get("/")

    assert response.status_code == 200
    result = response.json()
    assert result["service"] == "Knowledge Database API"
    assert result["version"] == "1.0.0"
    assert "features" in result
    assert "endpoints" in result

    # 验证功能描述
    features = result["features"]
    assert "knowledge_management" in features
    assert "dify_integration" in features
    assert "semantic_search" in features

    # 验证端点信息
    endpoints = result["endpoints"]
    assert "knowledge_management" in endpoints
    assert "dify_integration" in endpoints
    assert "system" in endpoints


# Dify API 增强测试
def test_retrieval_endpoint_basic():
    """测试基本的检索功能"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
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
                        "knowledge_type": "faq",
                    },
                }
            ]
        }
        mock_retrieve.return_value = mock_records

        # 准备测试请求
        request_data = {
            "knowledge_id": "lib_123",
            "query": "test retrieval query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.6},
        }

        # 添加授权头
        headers = {"Authorization": "Bearer your-api-key"}

        # 发送请求
        response = client.post("/retrieval", json=request_data, headers=headers)

        # 验证响应格式符合Dify标准
        assert response.status_code == 200
        result = response.json()
        assert "records" in result
        assert len(result["records"]) == 1

        record = result["records"][0]
        assert "content" in record
        assert "score" in record
        assert "title" in record
        assert "metadata" in record

        # 验证函数调用
        mock_check.assert_called_once_with(request_data["knowledge_id"])
        mock_retrieve.assert_called_once_with(
            knowledge_id=request_data["knowledge_id"],
            query=request_data["query"],
            top_k=request_data["retrieval_setting"]["top_k"],
            score_threshold=request_data["retrieval_setting"]["score_threshold"],
            metadata_condition=None,
        )


def test_retrieval_with_dify_api_key():
    """测试使用Dify风格的API密钥（长度>10位）"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}

        request_data = {
            "knowledge_id": "lib_123",
            "query": "test query",
            "retrieval_setting": {"top_k": 3, "score_threshold": 0.5},
        }

        # 使用Dify风格的长API密钥
        headers = {"Authorization": "Bearer dify-api-key-123456789"}

        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200
        mock_check.assert_called_once()


def test_retrieval_nonexistent_knowledge():
    """测试不存在的知识库"""
    with patch("dify_kg_ext.api.check_knowledge_exists") as mock_check:
        # 设置知识库不存在
        mock_check.return_value = False

        # 准备测试请求
        request_data = {
            "knowledge_id": "nonexistent_lib",
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.6},
        }

        # 添加授权头
        headers = {"Authorization": "Bearer your-api-key"}

        # 发送请求
        response = client.post("/retrieval", json=request_data, headers=headers)

        # 验证响应
        assert response.status_code == 404
        result = response.json()
        assert result["error_code"] == 2001
        assert "knowledge base does not exist" in result["error_msg"]


def test_retrieval_authentication_scenarios():
    """测试各种认证场景"""
    request_data = {
        "knowledge_id": "lib_123",
        "query": "test query",
        "retrieval_setting": {"top_k": 5, "score_threshold": 0.6},
    }

    # 1. 没有授权头
    response = client.post("/retrieval", json=request_data)
    assert response.status_code == 403
    assert response.json()["error_code"] == 1001
    assert "Missing Authorization header" in response.json()["error_msg"]

    # 2. 错误格式的授权头（没有空格）
    headers = {"Authorization": "BearerInvalidFormat"}
    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["error_code"] == 1001

    # 3. 错误的认证方案
    headers = {"Authorization": "Basic invalid-scheme"}
    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["error_code"] == 1001

    # 4. API密钥过短
    headers = {"Authorization": "Bearer short"}
    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["error_code"] == 1002
    assert "Authorization failed" in response.json()["error_msg"]


def test_retrieval_with_metadata_condition():
    """测试带元数据过滤条件的检索"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        # 设置知识库存在并返回结果
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}

        # 准备带元数据条件的测试请求
        request_data = {
            "knowledge_id": "lib_123",
            "query": "test query with metadata",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.6},
            "metadata_condition": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "name": ["category"],
                        "comparison_operator": "contains",
                        "value": "test",
                    }
                ],
            },
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


def test_retrieval_with_complex_metadata():
    """测试复杂元数据过滤条件"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}

        request_data = {
            "knowledge_id": "lib_123",
            "query": "complex metadata query",
            "retrieval_setting": {"top_k": 10, "score_threshold": 0.3},
            "metadata_condition": {
                "logical_operator": "or",
                "conditions": [
                    {
                        "name": ["knowledge_type"],
                        "comparison_operator": "eq",
                        "value": "faq",
                    },
                    {
                        "name": ["category_id"],
                        "comparison_operator": "in",
                        "value": "cat_123",
                    },
                ],
            },
        }

        headers = {"Authorization": "Bearer complex-test-api-key-123456"}
        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200
        mock_retrieve.assert_called_once()


def test_retrieval_edge_cases():
    """测试边界情况"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True

        # 测试空结果
        mock_retrieve.return_value = {"records": []}

        request_data = {
            "knowledge_id": "lib_123",
            "query": "no results query",
            "retrieval_setting": {
                "top_k": 1,
                "score_threshold": 0.99,  # 很高的阈值
            },
        }

        headers = {"Authorization": "Bearer edge-case-test-key-123"}
        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200
        result = response.json()
        assert "records" in result
        assert len(result["records"]) == 0


def test_retrieval_parameter_validation():
    """测试参数验证"""
    headers = {"Authorization": "Bearer valid-test-key-123456"}

    # 测试缺少必需参数
    invalid_requests = [
        # 缺少knowledge_id
        {
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
        },
        # 缺少query
        {
            "knowledge_id": "lib_123",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
        },
        # 缺少retrieval_setting
        {"knowledge_id": "lib_123", "query": "test query"},
        # top_k超出范围
        {
            "knowledge_id": "lib_123",
            "query": "test query",
            "retrieval_setting": {"top_k": 101, "score_threshold": 0.5},
        },
        # score_threshold超出范围
        {
            "knowledge_id": "lib_123",
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 1.5},
        },
    ]

    for invalid_request in invalid_requests:
        response = client.post("/retrieval", json=invalid_request, headers=headers)
        assert response.status_code == 422  # Validation error


# 异常处理测试
def test_retrieval_internal_error():
    """测试内部错误处理"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True
        # 模拟内部错误
        mock_retrieve.side_effect = Exception("Database connection failed")

        request_data = {
            "knowledge_id": "lib_123",
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.6},
        }

        headers = {"Authorization": "Bearer error-test-key-123456"}

        # The exception should be caught by the general exception handler
        # and return a 500 status with custom error format
        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 500
        result = response.json()
        assert result["error_code"] == 5001
        assert "Internal server error" in result["error_msg"]
        assert "Database connection failed" in result["error_msg"]


def test_retrieval_logging():
    """测试日志记录功能"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve, patch("dify_kg_ext.api.logger") as mock_logger:
        mock_check.return_value = True
        mock_retrieve.return_value = {
            "records": [
                {"content": "test", "score": 0.8, "title": "test", "metadata": {}}
            ]
        }

        request_data = {
            "knowledge_id": "lib_123",
            "query": "logging test query",
            "retrieval_setting": {"top_k": 3, "score_threshold": 0.5},
        }

        headers = {"Authorization": "Bearer logging-test-key-123456"}
        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200

        # 验证日志调用
        assert mock_logger.info.call_count >= 2  # 请求和响应日志

        # 验证日志内容
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("Knowledge retrieval request" in log for log in log_calls)
        assert any("Knowledge retrieval response" in log for log in log_calls)


# 性能和并发测试
def test_retrieval_concurrent_requests():
    """测试并发请求处理"""
    import threading
    import time

    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}

        def make_request(thread_id):
            request_data = {
                "knowledge_id": f"lib_{thread_id}",
                "query": f"concurrent test query {thread_id}",
                "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
            }

            headers = {
                "Authorization": f"Bearer concurrent-test-key-{thread_id}-123456"
            }
            response = client.post("/retrieval", json=request_data, headers=headers)
            return response.status_code

        # 创建多个线程并发请求
        threads = []
        results = []

        for i in range(5):
            thread = threading.Thread(
                target=lambda i=i: results.append(make_request(i))
            )
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有请求都成功
        assert len(results) == 5
        assert all(status == 200 for status in results)


# 兼容性测试
def test_backward_compatibility():
    """测试向后兼容性"""
    with patch(
        "dify_kg_ext.api.check_knowledge_exists"
    ) as mock_check, patch(
        "dify_kg_ext.api.retrieve_knowledge"
    ) as mock_retrieve:
        mock_check.return_value = True
        mock_retrieve.return_value = {"records": []}

        # 使用原有的API密钥格式
        headers = {"Authorization": "Bearer your-api-key"}

        request_data = {
            "knowledge_id": "lib_123",
            "query": "backward compatibility test",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
        }

        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200
        mock_check.assert_called_once()
        mock_retrieve.assert_called_once()


def test_api_documentation_endpoints():
    """测试API文档相关端点"""
    # 测试OpenAPI文档端点
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()
    assert "openapi" in openapi_spec
    assert "info" in openapi_spec
    assert openapi_spec["info"]["title"] == "Knowledge Database API"

    # 验证关键端点在文档中
    paths = openapi_spec["paths"]
    assert "/retrieval" in paths
    assert "/health" in paths
    assert "/knowledge/update" in paths


def test_upload_document():
    """Test document upload endpoint"""
    request = UploadDocumentRequest(file_path="http://example.com/test.pdf")
    response = client.post("/upload_document", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["sign"] is True
    assert len(data["dataset_id"]) == 32  # UUID without hyphens
    assert len(data["document_id"]) == 32
    assert len(data["part_document_id"]) == 32
    assert data["document_name"] == "test.pdf"
    assert data["part_document_name"] == "part_test.pdf"


def test_analyzing_document():
    """Test document parsing endpoint"""
    # Mock the Celery task
    with patch("dify_kg_ext.api.parse_document_task.delay") as mock_task:
        # Setup mock task result
        mock_result = mock_task.return_value
        mock_result.get.return_value = [
            {"text": "First chunk content"},
            {"text": "Second chunk content"},
            {"other_field": "Invalid chunk"},
        ]

        request = AnalyzingDocumentRequest(
            dataset_id="dataset_123",
            document_id="doc_456",
            document_name="test.pdf",
            chunk_method="naive",
            parser_flag=0,
            parser_config={},
        )

        response = client.post("/analyzing_document", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["sign"] is True
        assert data["chunks"] == [
            "First chunk content",
            "Second chunk content",
            "{'other_field': 'Invalid chunk'}",  # Fallback for invalid chunks
        ]

        # Verify task was called with correct arguments
        mock_task.assert_called_once_with("/tmp/test.pdf")


def test_analyzing_document_with_custom_config():
    """Test document parsing with custom parser configuration"""
    with patch("dify_kg_ext.api.parse_document_task.delay") as mock_task:
        mock_result = mock_task.return_value
        mock_result.get.return_value = [{"text": "Chunk content"}]

        request = AnalyzingDocumentRequest(
            dataset_id="dataset_123",
            document_id="doc_456",
            document_name="test.pdf",
            chunk_method="laws",
            parser_flag=1,
            parser_config={
                "chunk_token_count": 256,
                "task_page_size": 50,
                "layout_recognize": True,
            },
        )

        response = client.post("/analyzing_document", json=request.model_dump())

        assert response.status_code == 200
        mock_task.assert_called_once_with(
            "/tmp/test.pdf", max_tokens=256, max_num_pages=50
        )


def test_analyzing_document_timeout():
    """Test document parsing timeout handling"""
    with patch("dify_kg_ext.api.parse_document_task.delay") as mock_task:
        mock_result = mock_task.return_value
        mock_result.get.side_effect = TimeoutError("Task timed out")

        request = AnalyzingDocumentRequest(
            dataset_id="dataset_123",
            document_id="doc_456",
            document_name="test.pdf",
            chunk_method="naive",
            parser_flag=0,
        )

        response = client.post("/analyzing_document", json=request.model_dump())

        assert response.status_code == 500
        error_detail = response.json()
        assert error_detail["error_code"] == 5001
        assert "Task timed out" in error_detail["error_msg"]


def test_analyzing_document_invalid_file():
    """Test handling of invalid file paths"""
    with patch("dify_kg_ext.api.parse_document_task.delay") as mock_task:
        mock_result = mock_task.return_value
        mock_result.get.side_effect = FileNotFoundError("File not found")

        request = AnalyzingDocumentRequest(
            dataset_id="dataset_123",
            document_id="doc_456",
            document_name="missing.pdf",
            chunk_method="naive",
            parser_flag=0,
        )

        response = client.post("/analyzing_document", json=request.model_dump())

        assert response.status_code == 500
        error_detail = response.json()
        assert error_detail["error_code"] == 5001
        assert "File not found" in error_detail["error_msg"]