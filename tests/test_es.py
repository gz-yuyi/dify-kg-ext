from unittest.mock import AsyncMock, patch

import pytest
from dify_kg_ext.dataclasses import Answer, Knowledge
from dify_kg_ext.es import (
    BINDING_INDEX,
    KNOWLEDGE_INDEX,
    VECTOR_INDEX,
    bind_knowledge_to_library,
    check_knowledge_exists,
    delete_documents,
    index_document,
    retrieve_knowledge,
    search_knowledge,
    unbind_knowledge_from_library,
)
from pytest import approx


@pytest.fixture
def mock_es_client():
    with patch("dify_kg_ext.es.es_client") as mock_client:
        # Configure mock to work with async calls
        mock_client.indices.exists = AsyncMock(return_value=True)
        mock_client.indices.create = AsyncMock(return_value={"acknowledged": True})
        mock_client.bulk = AsyncMock(return_value={"errors": False})
        mock_client.delete_by_query = AsyncMock(return_value={"deleted": 2})
        mock_client.search = AsyncMock()
        mock_client.get = AsyncMock()
        mock_client.index = AsyncMock(return_value={"_id": "test_id"})
        mock_client.exists = AsyncMock()

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
        category_id="cat_456",
    )


@pytest.fixture
def mock_embedding():
    with patch("dify_kg_ext.es.embedding", new_callable=AsyncMock) as mock_embed:
        # Return a simple mock vector of appropriate dimension
        mock_embed.return_value = [0.1] * 1024
        yield mock_embed


@pytest.mark.asyncio
async def test_index_document(mock_es_client, mock_embedding, sample_knowledge):
    # Set up mock search response
    mock_es_client.search.return_value = {"hits": {"hits": [{"_id": "vec_1"}]}}

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
        "hits": {"hits": [{"_id": "vec_1"}, {"_id": "vec_2"}]}
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
        library_id="lib_123", category_ids=["cat_1", "cat_2"]
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
        library_id="lib_123", category_ids=["cat_1", "cat_2"], delete_type="all"
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
        "found": True,
        "_source": {"category_id": ["cat_1", "cat_2"]},
    }

    # Set up mock response for knowledge search
    mock_es_client.search.side_effect = [
        # First search call (vector search)
        {"hits": {"hits": [{"_source": {"segment_id": "segment_123"}}]}},
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
                            "category_id": "cat_456",
                        }
                    }
                ]
            }
        },
    ]

    # Call the function
    result = await search_knowledge(query="test query", library_id="lib_123", limit=10)

    # Verify embedding was called with query
    mock_embedding.assert_called_once_with("test query")

    # Verify get was called to fetch categories
    mock_es_client.get.assert_called_once()

    # Verify search was called twice
    assert mock_es_client.search.call_count == 2

    # Verify result structure
    assert "segments" in result
    assert len(result["segments"]) == 1
    assert isinstance(result["segments"][0], Knowledge)
    assert result["segments"][0].segment_id == "segment_123"


@pytest.mark.asyncio
async def test_check_knowledge_exists(mock_es_client):
    # 设置mock响应为AsyncMock而不是普通bool
    mock_es_client.exists.return_value = True

    # 调用函数
    result = await check_knowledge_exists("lib_123")

    # 验证exists调用
    mock_es_client.exists.assert_called_once_with(index=BINDING_INDEX, id="lib_123")

    # 验证返回值
    assert result is True

    # 重置mock并测试不存在的情况
    mock_es_client.exists.reset_mock()
    mock_es_client.exists.return_value = False

    result = await check_knowledge_exists("non_existent_lib")
    assert result is False


@pytest.mark.asyncio
async def test_retrieve_knowledge(mock_es_client, mock_embedding):
    # 设置知识库存在的mock响应
    mock_es_client.exists.return_value = True

    # 设置binding文档的mock响应
    mock_es_client.get.side_effect = [
        # 第一次调用get (binding查询)
        {"found": True, "_source": {"category_id": ["cat_1", "cat_2"]}},
        # 第二次调用get (第一个知识文档)
        {
            "found": True,
            "_source": {
                "segment_id": "segment_123",
                "question": "Sample question",
                "document_id": "doc_456",
                "category_id": "cat_1",
                "knowledge_type": "faq",
                "keywords": ["keyword1", "keyword2"],
            },
        },
        # 第三次调用get (第二个知识文档)
        {
            "found": True,
            "_source": {
                "segment_id": "segment_456",
                "question": "Another question",
                "document_id": "doc_789",
                "category_id": "cat_2",
                "knowledge_type": "segment",
            },
        },
    ]

    # 设置向量搜索结果的mock响应
    mock_es_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 1.85,  # 0.85 after normalization
                    "_source": {
                        "segment_id": "segment_123",
                        "text": "This is a sample text content",
                        "category_id": "cat_1",
                    },
                },
                {
                    "_score": 1.75,  # 0.75 after normalization
                    "_source": {
                        "segment_id": "segment_456",
                        "text": "This is another text content",
                        "category_id": "cat_2",
                    },
                },
                {
                    "_score": 1.45,  # 0.45 after normalization - below threshold
                    "_source": {
                        "segment_id": "segment_789",
                        "text": "Low score content",
                        "category_id": "cat_1",
                    },
                },
            ]
        }
    }

    # 调用函数
    result = await retrieve_knowledge(
        knowledge_id="lib_123", query="test query", top_k=3, score_threshold=0.5
    )

    # 验证调用
    mock_embedding.assert_called_once_with("test query")
    mock_es_client.exists.assert_called_once()
    assert mock_es_client.get.call_count == 3
    mock_es_client.search.assert_called_once()

    # 验证结果
    assert "records" in result
    assert len(result["records"]) == 2  # 第三个结果低于阈值

    # 验证第一条记录
    assert result["records"][0]["content"] == "This is a sample text content"
    assert result["records"][0]["score"] == approx(0.85)
    assert result["records"][0]["title"] == "Sample question"
    assert "metadata" in result["records"][0]
    assert result["records"][0]["metadata"]["document_id"] == "doc_456"
    assert "keywords" in result["records"][0]["metadata"]

    # 验证第二条记录
    assert result["records"][1]["content"] == "This is another text content"
    assert result["records"][1]["score"] == approx(0.75)
    assert result["records"][1]["title"] == "Another question"


@pytest.mark.asyncio
async def test_retrieve_knowledge_empty_results(mock_es_client, mock_embedding):
    # 设置知识库存在但无结果的情况
    mock_es_client.exists.return_value = True
    mock_es_client.get.return_value = {
        "found": True,
        "_source": {"category_id": ["cat_1"]},
    }
    mock_es_client.search.return_value = {"hits": {"hits": []}}

    result = await retrieve_knowledge(
        knowledge_id="lib_123", query="no results query", top_k=5
    )

    assert "records" in result
    assert len(result["records"]) == 0


@pytest.mark.asyncio
async def test_retrieve_knowledge_nonexistent_knowledge(mock_es_client):
    # 设置知识库不存在的情况
    mock_es_client.exists.return_value = False

    result = await retrieve_knowledge(
        knowledge_id="nonexistent_lib", query="test query"
    )

    # 验证结果
    assert "records" in result
    assert len(result["records"]) == 0

    # 验证不调用其他方法
    mock_es_client.get.assert_not_called()
    mock_es_client.search.assert_not_called()