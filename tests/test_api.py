from unittest.mock import patch

from fastapi.testclient import TestClient

from dify_kg_ext.api import app
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
    TextChunkingRequest,
    UploadDocumentRequest,
)


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
        assert "Failed to index document" in response.json()["detail"]


def test_delete_knowledge():
    with patch("dify_kg_ext.api.delete_documents") as mock_delete:
        mock_delete.return_value = True

        request = KnowledgeDeleteRequest(segment_ids=["segment_123", "segment_456"])

        response = client.post("/knowledge/delete", json=request.model_dump())

        assert response.status_code == 200
        assert response.json() == {"code": 200, "msg": "success"}
        mock_delete.assert_called_once_with(request.segment_ids)


def test_delete_knowledge_failure():
    with patch("dify_kg_ext.api.delete_documents") as mock_delete:
        mock_delete.return_value = False

        request = KnowledgeDeleteRequest(segment_ids=["segment_123", "segment_456"])

        response = client.post("/knowledge/delete", json=request.model_dump())

        assert response.status_code == 500
        assert "Failed to delete documents" in response.json()["detail"]


def test_bind_knowledge_batch():
    with patch("dify_kg_ext.api.bind_knowledge_to_library") as mock_bind:
        mock_bind.return_value = {"success_count": 1, "failed_ids": []}

        request = KnowledgeBindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2"]
        )

        response = client.post("/knowledge/bind_batch", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["msg"] == "success"
        assert data["data"]["success_count"] == 1
        assert data["data"]["failed_ids"] == []
        mock_bind.assert_called_once_with(request.library_id, request.category_ids)


def test_bind_knowledge_batch_failure():
    with patch("dify_kg_ext.api.bind_knowledge_to_library") as mock_bind:
        mock_bind.return_value = {"success_count": 0, "failed_ids": ["cat_1", "cat_2"]}

        request = KnowledgeBindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2"]
        )

        response = client.post("/knowledge/bind_batch", json=request.model_dump())

        assert response.status_code == 500
        assert "Failed to bind knowledge" in response.json()["detail"]


def test_unbind_knowledge_batch():
    with patch("dify_kg_ext.api.unbind_knowledge_from_library") as mock_unbind:
        mock_unbind.return_value = {"success_count": 1, "failed_ids": []}

        request = KnowledgeUnbindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2"], delete_type="part"
        )

        response = client.post("/knowledge/unbind_batch", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["msg"] == "success"
        assert data["data"]["success_count"] == 1
        assert data["data"]["failed_ids"] == []
        mock_unbind.assert_called_once_with(
            request.library_id, request.category_ids, request.delete_type
        )


def test_unbind_knowledge_batch_failure():
    with patch("dify_kg_ext.api.unbind_knowledge_from_library") as mock_unbind:
        mock_unbind.return_value = None  # 返回None表示失败

        request = KnowledgeUnbindBatchRequest(
            library_id="lib_123", category_ids=["cat_1", "cat_2"], delete_type="part"
        )

        response = client.post("/knowledge/unbind_batch", json=request.model_dump())

        assert response.status_code == 500
        assert "Failed to unbind knowledge" in response.json()["detail"]


def test_search_knowledge():
    with patch("dify_kg_ext.api.search_knowledge") as mock_search:
        # 返回完整的Knowledge对象
        from dify_kg_ext.dataclasses import Answer, Knowledge

        mock_knowledge = Knowledge(
            segment_id="seg_1",
            source="personal",
            knowledge_type="faq",
            question="What is AI?",
            answers=[Answer(content="Artificial Intelligence...", channels=["web"])],
            weight=5,
            category_id="cat_001",
        )
        mock_search.return_value = {"segments": [mock_knowledge]}

        request = KnowledgeSearchRequest(
            query="artificial intelligence", library_id="lib_123", limit=10
        )

        response = client.post("/knowledge/search", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["msg"] == "success"
        assert len(data["data"]["segments"]) == 1
        mock_search.assert_called_once_with(
            query=request.query, library_id=request.library_id, limit=request.limit
        )


def test_retrieval():
    with (
        patch("dify_kg_ext.api.check_knowledge_exists") as mock_check,
        patch("dify_kg_ext.api.retrieve_knowledge") as mock_retrieve,
    ):
        mock_check.return_value = True
        mock_retrieve.return_value = {
            "records": [
                {
                    "content": "Test content",
                    "score": 0.95,
                    "title": "Test Document",
                    "metadata": {"source": "test"},
                }
            ]
        }

        headers = {"Authorization": "Bearer test-api-key-123"}
        request_data = {
            "knowledge_id": "kb_123",
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
        }

        response = client.post("/retrieval", json=request_data, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) == 1
        assert data["records"][0]["content"] == "Test content"
        assert data["records"][0]["score"] == 0.95


def test_retrieval_invalid_api_key():
    headers = {"Authorization": "Bearer short"}
    request_data = {
        "knowledge_id": "kb_123",
        "query": "test query",
        "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
    }

    response = client.post("/retrieval", json=request_data, headers=headers)
    assert response.status_code == 403


def test_retrieval_knowledge_not_found():
    with patch("dify_kg_ext.api.check_knowledge_exists") as mock_check:
        mock_check.return_value = False

        headers = {"Authorization": "Bearer test-api-key-123"}
        request_data = {
            "knowledge_id": "kb_nonexistent",
            "query": "test query",
            "retrieval_setting": {"top_k": 5, "score_threshold": 0.5},
        }

        response = client.post("/retrieval", json=request_data, headers=headers)
        assert response.status_code == 404


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Knowledge Database API"
    assert "features" in data
    assert "endpoints" in data


# RAGFlow相关的文档处理测试用例


def test_upload_document():
    """测试使用RAGFlow上传文档"""
    with patch("dify_kg_ext.api.upload_and_parse_document") as mock_upload:
        mock_upload.return_value = {
            "dataset_id": "ragflow_dataset_123",
            "document_id": "ragflow_doc_456",
            "chunks": ["chunk1", "chunk2", "chunk3"],
            "status": "completed",
        }

        request = UploadDocumentRequest(file_path="http://example.com/test.pdf")
        response = client.post("/upload_documents", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["sign"] is True
        assert len(data["dataset_id"]) == 32  # UUID without hyphens
        assert len(data["document_id"]) == 32
        assert len(data["part_document_id"]) == 32
        assert data["document_name"] == "test.pdf"
        assert data["part_document_name"] == "part_test.pdf"

        mock_upload.assert_called_once_with(
            file_path="http://example.com/test.pdf",
            dataset_name=f"dataset_{data['dataset_id']}",
            chunk_method="naive",
        )


def test_upload_document_ragflow_failure():
    """测试RAGFlow上传失败的情况"""
    with patch("dify_kg_ext.api.upload_and_parse_document") as mock_upload:
        mock_upload.side_effect = Exception("RAGFlow connection failed")

        request = UploadDocumentRequest(file_path="http://example.com/test.pdf")
        response = client.post("/upload_documents", json=request.model_dump())

        assert response.status_code == 500


def test_analyzing_document_from_cache():
    """测试从缓存中获取文档分析结果"""
    # 先模拟缓存中有数据
    document_id = "cached_doc_123"
    from dify_kg_ext.api import document_cache

    document_cache[document_id] = {
        "dataset_id": "dataset_456",
        "document_id": "ragflow_doc_789",
        "chunks": ["Cached chunk 1", "Cached chunk 2"],
        "status": "completed",
    }

    request = AnalyzingDocumentRequest(
        dataset_id="dataset_456",
        document_id=document_id,
        document_name="cached_doc.pdf",
        chunk_method="naive",
        parser_flag=0,
        parser_config={},
    )

    response = client.post("/analyzing_documents", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["sign"] is True
    assert len(data["chunks"]) == 2
    assert data["chunks"] == ["Cached chunk 1", "Cached chunk 2"]

    # 清理缓存
    del document_cache[document_id]


def test_analyzing_document_not_found():
    """测试分析不存在的文档"""
    request = AnalyzingDocumentRequest(
        dataset_id="dataset_123",
        document_id="nonexistent_doc",
        document_name="missing.pdf",
        chunk_method="naive",
        parser_flag=0,
        parser_config={},
    )

    response = client.post("/analyzing_documents", json=request.model_dump())

    assert response.status_code == 404
    error_detail = response.json()
    assert error_detail["detail"]["error_code"] == 2001
    assert "Document not found" in error_detail["detail"]["error_msg"]


def test_analyzing_document_with_custom_config():
    """测试使用自定义配置分析文档"""
    document_id = "custom_config_doc"
    from dify_kg_ext.api import document_cache

    document_cache[document_id] = {
        "dataset_id": "dataset_456",
        "document_id": "ragflow_doc_789",
        "chunks": ["Custom chunk with laws method"],
        "status": "completed",
    }

    request = AnalyzingDocumentRequest(
        dataset_id="dataset_456",
        document_id=document_id,
        document_name="legal_doc.pdf",
        chunk_method="laws",
        parser_flag=1,
        parser_config={"chunk_token_count": 256, "layout_recognize": True},
    )

    response = client.post("/analyzing_documents", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["sign"] is True
    assert data["chunks"] == ["Custom chunk with laws method"]

    # 清理缓存
    del document_cache[document_id]


def test_chunk_text_success():
    """测试使用RAGFlow成功进行文本分块"""
    with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
        mock_chunk.return_value = [
            "First text chunk from RAGFlow",
            "Second text chunk from RAGFlow",
        ]

        request = TextChunkingRequest(
            text="This is a long text that needs to be chunked using RAGFlow...",
            chunk_method="naive",
            parser_flag=0,
            parser_config={},
        )

        response = client.post("/chunk_text", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["sign"] is True
        assert len(data["chunks"]) == 2
        assert data["chunks"] == [
            "First text chunk from RAGFlow",
            "Second text chunk from RAGFlow",
        ]

        mock_chunk.assert_called_once_with(
            text=request.text,
            chunk_method=request.chunk_method,
            parser_config=None,  # parser_flag=0时传递None
        )


def test_chunk_text_with_parser_config():
    """测试使用自定义配置进行文本分块"""
    with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
        mock_chunk.return_value = ["Custom configured chunk"]

        request = TextChunkingRequest(
            text="Text with custom configuration for chunking",
            chunk_method="book",
            parser_flag=1,
            parser_config={"chunk_token_count": 256, "delimiter": "\n\n"},
        )

        response = client.post("/chunk_text", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["sign"] is True
        assert len(data["chunks"]) == 1
        assert data["chunks"] == ["Custom configured chunk"]

        mock_chunk.assert_called_once_with(
            text=request.text,
            chunk_method=request.chunk_method,
            parser_config=request.parser_config,  # parser_flag=1时传递实际配置
        )


def test_chunk_text_different_methods():
    """测试不同的分块方法"""
    methods = ["naive", "qa", "table", "laws", "email", "book", "paper"]

    for method in methods:
        with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
            mock_chunk.return_value = [f"Chunk using {method} method"]

            request = TextChunkingRequest(
                text=f"Sample text for {method} chunking method",
                chunk_method=method,
                parser_flag=0,
                parser_config={},
            )

            response = client.post("/chunk_text", json=request.model_dump())
            assert response.status_code == 200
            data = response.json()
            assert len(data["chunks"]) == 1
            assert method in data["chunks"][0]


def test_chunk_text_ragflow_failure():
    """测试RAGFlow分块失败的情况"""
    with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
        mock_chunk.side_effect = Exception("RAGFlow chunking failed")

        request = TextChunkingRequest(
            text="Problematic text that causes RAGFlow to fail",
            chunk_method="naive",
            parser_flag=0,
            parser_config={},
        )

        response = client.post("/chunk_text", json=request.model_dump())

        assert response.status_code == 500


def test_chunk_text_no_parser_config():
    """测试不使用parser配置的情况"""
    with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
        mock_chunk.return_value = ["Simple chunk without config"]

        request = TextChunkingRequest(
            text="Simple text without parser configuration",
            chunk_method="naive",
            parser_flag=0,
            parser_config={},
        )

        response = client.post("/chunk_text", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["chunks"] == ["Simple chunk without config"]

        # 验证传递给RAGFlow的参数
        mock_chunk.assert_called_once_with(
            text=request.text,
            chunk_method=request.chunk_method,
            parser_config=None,  # parser_flag=0时应该传递None
        )


def test_chunk_text_edge_cases():
    """测试边界情况"""
    test_cases = [
        {
            "text": "A",  # 最短的有效文本
            "expected_chunks": ["Single character chunk"],
        },
        {
            "text": "A" * 10000,  # 很长的文本
            "expected_chunks": ["Long text chunk 1", "Long text chunk 2"],
        },
        {
            "text": "Short",  # 很短的文本
            "expected_chunks": ["Short"],
        },
    ]

    for i, case in enumerate(test_cases):
        with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
            mock_chunk.return_value = case["expected_chunks"]

            request = TextChunkingRequest(
                text=case["text"], chunk_method="naive", parser_flag=0, parser_config={}
            )

            response = client.post("/chunk_text", json=request.model_dump())

            assert response.status_code == 200
            data = response.json()
            assert data["chunks"] == case["expected_chunks"], f"Test case {i} failed"


def test_chunk_text_performance():
    """测试分块性能相关的功能"""
    with patch("dify_kg_ext.api.chunk_text_directly") as mock_chunk:
        # 模拟返回大量分块
        large_chunks = [f"Chunk {i}" for i in range(100)]
        mock_chunk.return_value = large_chunks

        request = TextChunkingRequest(
            text="Very large document content that should be split into many chunks...",
            chunk_method="naive",
            parser_flag=1,
            parser_config={"chunk_token_count": 50},  # 小的token数量产生更多分块
        )

        response = client.post("/chunk_text", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert len(data["chunks"]) == 100
        assert all(chunk.startswith("Chunk") for chunk in data["chunks"])
