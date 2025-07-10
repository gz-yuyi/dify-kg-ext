import json
import os
from typing import List

import elasticsearch

from dify_kg_ext import APP_NAME
from dify_kg_ext.adapters import embedding
from dify_kg_ext.dataclasses import Knowledge

DIM_SIZE = 1024

# Define index names with prefix
VECTOR_INDEX = f"{APP_NAME}_vector_index"
KNOWLEDGE_INDEX = f"{APP_NAME}_knowledge_index"
BINDING_INDEX = f"{APP_NAME}_binding_index"  # New index for library-category bindings

# Vector mapping with type field to distinguish question/answer vectors
vector_mapping = {
    "mappings": {
        "properties": {
            "segment_id": {"type": "keyword"},
            "vector_type": {"type": "keyword"},  # "question" or "answer"
            "vector": {
                "type": "dense_vector",
                "dims": DIM_SIZE,
                "index": True,
                "similarity": "cosine",
            },
            "text": {
                "type": "text",
                "analyzer": "standard",
            },
            "category_id": {"type": "keyword"},
        }
    }
}

# Main knowledge data mapping with segment_id as primary key
knowledge_mapping = {
    "mappings": {
        "properties": {
            "segment_id": {"type": "keyword"},
            "source": {"type": "keyword"},
            "knowledge_type": {"type": "keyword"},
            "question": {
                "type": "text",
                "analyzer": "standard",
            },
            "similar_questions": {
                "type": "text",
                "analyzer": "standard",
            },
            "answers": {
                "type": "nested",
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "standard",
                    },
                    "channels": {"type": "keyword"},
                },
            },
            "weight": {"type": "integer"},
            "document_id": {"type": "keyword"},
            "keywords": {"type": "keyword"},
            "category_id": {"type": "keyword"},
        },
    }
}

# New mapping for library-category binding relationships
binding_mapping = {
    "mappings": {
        "properties": {
            "library_id": {"type": "keyword"},
            "category_id": {"type": "keyword"},
        },
        "dynamic": "strict",
    }
}

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
es_client = elasticsearch.AsyncElasticsearch(
    [ES_HOST], basic_auth=("elastic", "telecom12345")
)


def ensure_index_exists_decorator(func):
    """Decorator that ensures all required Elasticsearch indices exist before executing the decorated function"""

    async def wrapper(*args, **kwargs):
        # Check and create vector index
        if not await es_client.indices.exists(index=VECTOR_INDEX, ignore=[400, 404]):
            await es_client.indices.create(index=VECTOR_INDEX, body=vector_mapping)

        # Check and create knowledge index
        if not await es_client.indices.exists(index=KNOWLEDGE_INDEX, ignore=[400, 404]):
            await es_client.indices.create(
                index=KNOWLEDGE_INDEX, body=knowledge_mapping
            )

        # Check and create binding index
        if not await es_client.indices.exists(index=BINDING_INDEX, ignore=[400, 404]):
            await es_client.indices.create(index=BINDING_INDEX, body=binding_mapping)

        # Call the decorated function
        return await func(*args, **kwargs)

    return wrapper


@ensure_index_exists_decorator
async def index_document(doc: "Knowledge"):
    """Index a knowledge document using bulk operations for better atomicity"""
    # First delete all vectors associated with this segment_id
    delete_query = {"term": {"segment_id": doc.segment_id}}
    await es_client.delete_by_query(
        index=VECTOR_INDEX, query=delete_query, ignore=[404, 400]
    )

    # Generate embeddings
    question_vector = None
    answer_vector = None

    # Generate embedding for the main question
    if doc.question:
        question_vector = await embedding(doc.question)

    # Generate embedding for the first answer
    if doc.answers:
        answer_content = doc.answers[0].content
        answer_vector = await embedding(answer_content)

    # Prepare bulk operations
    bulk_operations = []

    # Add knowledge document operation
    knowledge_doc = {
        "segment_id": doc.segment_id,
        "source": doc.source,
        "knowledge_type": doc.knowledge_type,
        "question": doc.question,
        "similar_questions": doc.similar_questions,
        "answers": [
            {"content": answer.content, "channels": answer.channels}
            for answer in doc.answers
        ],
        "weight": doc.weight,
        "document_id": doc.document_id,
        "keywords": doc.keywords,
        "category_id": doc.category_id,
    }

    # Index operation for knowledge document
    bulk_operations.append(
        {"index": {"_index": KNOWLEDGE_INDEX, "_id": doc.segment_id}}
    )
    bulk_operations.append(knowledge_doc)

    # Add question vector document operation
    if question_vector:
        question_vector_doc = {
            "segment_id": doc.segment_id,
            "vector_type": "question",
            "vector": question_vector,
            "text": doc.question,
            "category_id": doc.category_id,
        }
        bulk_operations.append({"index": {"_index": VECTOR_INDEX}})
        bulk_operations.append(question_vector_doc)

        # Handle similar questions - add operations for each
        if doc.similar_questions:
            for similar_q in doc.similar_questions:
                similar_q_doc = {
                    "segment_id": doc.segment_id,
                    "vector_type": "similar_question",
                    "vector": question_vector,  # Using same vector as main question
                    "text": similar_q,
                    "category_id": doc.category_id,
                }
                bulk_operations.append({"index": {"_index": VECTOR_INDEX}})
                bulk_operations.append(similar_q_doc)

    # Add answer vector document operation
    if answer_vector:
        answer_content = doc.answers[0].content
        answer_vector_doc = {
            "segment_id": doc.segment_id,
            "vector_type": "answer",
            "vector": answer_vector,
            "text": answer_content,
            "category_id": doc.category_id,
        }
        bulk_operations.append({"index": {"_index": VECTOR_INDEX}})
        bulk_operations.append(answer_vector_doc)

    # Execute all operations in a single bulk request
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)

    return doc.segment_id


@ensure_index_exists_decorator
async def delete_documents(segment_ids: List[str]):
    """
    Delete multiple knowledge documents and their associated vectors by segment_ids
    using a single bulk operation for better atomicity.

    Args:
        segment_ids: List of segment_ids to delete
    """
    if not segment_ids:
        return

    # First find all vector documents for these segment_ids
    search_query = {"terms": {"segment_id": segment_ids}}

    vector_results = await es_client.search(
        index=VECTOR_INDEX,
        query=search_query,
        size=10000,  # Adjust as needed based on your data volume
        _source=False,  # We only need the IDs
    )

    # Prepare bulk delete operations for both knowledge and vector documents
    bulk_operations = []

    # Add knowledge document deletions
    for segment_id in segment_ids:
        bulk_operations.append(
            {"delete": {"_index": KNOWLEDGE_INDEX, "_id": segment_id}}
        )

    # Add vector document deletions
    for hit in vector_results["hits"]["hits"]:
        bulk_operations.append({"delete": {"_index": VECTOR_INDEX, "_id": hit["_id"]}})

    # Execute bulk delete for all documents in a single operation
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)


@ensure_index_exists_decorator
async def bind_knowledge_to_library(library_id: str, category_ids: List[str]):
    """
    Bind multiple knowledge documents to a library

    Args:
        library_id: The library ID to bind to
        category_ids: List of category IDs to bind

    Returns:
        Dict with success_count and failed_ids
    """
    if not category_ids or not library_id:
        return {"success_count": 0, "failed_ids": category_ids or []}
    # create binding document
    binding_doc = {
        "library_id": library_id,
        "category_id": category_ids,
    }
    await es_client.index(
        index=BINDING_INDEX, document=binding_doc, refresh=True, id=library_id
    )
    return {"success_count": 1, "failed_ids": []}


@ensure_index_exists_decorator
async def unbind_knowledge_from_library(
    library_id: str, category_ids: List[str] = None, delete_type: str = "all"
):
    """
    Unbind knowledge documents from a library

    Args:
        library_id: The library ID to unbind from
        category_ids: List of category IDs to unbind (used when delete_type is "part")
        delete_type: "all" to unbind all documents from library

    Returns:
        Dict with success_count and number of unbound documents
    """
    # 现在都是delete_type为all的逻辑，这里保留参数只是为了做兼容处理
    response = await es_client.delete_by_query(
        index=BINDING_INDEX,
        query={"term": {"library_id": library_id}},
        refresh=True,
    )
    return {"success_count": response["deleted"], "failed_ids": []}


async def search_knowledge(query: str, library_id: str, limit: int = 10):
    """
    Search for knowledge segments by query text within a specific library

    Args:
        query: The search query text
        library_id: The library ID to search within
        limit: Maximum number of results to return

    Returns:
        List of Knowledge objects matching the query
    """
    # Generate embedding for the query
    query_vector = await embedding(query)

    # First, get all category_ids bound to this library
    binding_result = await es_client.get(
        index=BINDING_INDEX, id=library_id, ignore=[400, 404]
    )

    if not binding_result.get("found", False):
        return {"segments": []}

    category_ids = binding_result["_source"]["category_id"]

    if not category_ids:
        return {"segments": []}

    # Use script_score query instead of KNN for better compatibility
    vector_query = {
        "script_score": {
            "query": {"terms": {"category_id": category_ids}},
            "script": {
                "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                "params": {"query_vector": query_vector},
            },
        }
    }

    # Search for matching knowledge
    vector_results = await es_client.search(
        index=VECTOR_INDEX, query=vector_query, size=limit
    )

    # Extract unique segment_ids from results
    segment_ids = list(
        set(hit["_source"]["segment_id"] for hit in vector_results["hits"]["hits"])
    )

    if not segment_ids:
        return {"segments": []}

    # Fetch the complete knowledge documents for these segment_ids
    knowledge_results = await es_client.search(
        index=KNOWLEDGE_INDEX, query={"terms": {"_id": segment_ids}}, size=limit
    )

    # Transform results into Knowledge objects
    knowledge_list = []
    for hit in knowledge_results["hits"]["hits"]:
        source = hit["_source"]
        knowledge = Knowledge(
            segment_id=source["segment_id"],
            source=source["source"],
            knowledge_type=source["knowledge_type"],
            question=source.get("question"),
            similar_questions=source.get("similar_questions", []),
            answers=[
                {"content": answer["content"], "channels": answer["channels"]}
                for answer in source.get("answers", [])
            ],
            weight=source.get("weight", 0),
            document_id=source.get("document_id"),
            keywords=source.get("keywords", []),
            category_id=source.get("category_id"),
        )
        knowledge_list.append(knowledge)

    return {"segments": knowledge_list}


async def check_knowledge_exists(knowledge_id: str) -> bool:
    """
    检查指定知识库ID是否存在

    Args:
        knowledge_id: 知识库ID

    Returns:
        bool: 知识库是否存在
    """
    # 改变实现方式，不要await布尔值
    exists_result = await es_client.exists(index=BINDING_INDEX, id=knowledge_id)
    return exists_result


async def retrieve_knowledge(
    knowledge_id: str,
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.5,
    metadata_condition=None,
):
    """
    从知识库检索数据

    Args:
        knowledge_id: 知识库ID（对应library_id）
        query: 用户查询
        top_k: 返回结果的最大数量
        score_threshold: 相关性分数阈值
        metadata_condition: 元数据过滤条件

    Returns:
        包含检索结果的记录列表
    """
    # 先检查知识库是否存在
    if not await check_knowledge_exists(knowledge_id):
        return {"records": []}

    # 生成查询的向量表示
    query_vector = await embedding(query)

    # 获取知识库绑定的所有category_ids
    binding_result = await es_client.get(
        index=BINDING_INDEX, id=knowledge_id, ignore=[400, 404]
    )

    if not binding_result.get("found", False):
        return {"records": []}

    category_ids = binding_result["_source"]["category_id"]

    if not category_ids:
        return {"records": []}

    # 使用script_score查询以获得更好的兼容性
    vector_query = {
        "script_score": {
            "query": {"terms": {"category_id": category_ids}},
            "script": {
                "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                "params": {"query_vector": query_vector},
            },
        }
    }

    # 应用元数据过滤条件
    if metadata_condition:
        # TODO 这里需要实现元数据过滤逻辑，暂未实现
        pass

    # 搜索匹配的知识
    vector_results = await es_client.search(
        index=VECTOR_INDEX, query=vector_query, size=top_k * 2
    )

    # 提取结果信息
    records = []

    segment_id_set = set()

    for hit in vector_results["hits"]["hits"]:
        source = hit["_source"]
        score = hit["_score"] - 1.0  # 还原余弦相似度范围到0-1
        segment_id = source["segment_id"]

        if (
            score < score_threshold
            or segment_id in segment_id_set
            or len(segment_id_set) > top_k
        ):
            continue

        # 获取完整知识文档，并处理可能的错误
        knowledge_doc = await es_client.get(
            index=KNOWLEDGE_INDEX, id=segment_id, ignore=[404]
        )

        # 如果文档不存在，跳过此结果
        if not knowledge_doc.get("found", False):
            continue

        knowledge_source = knowledge_doc["_source"]

        if knowledge_source.get(segment_id) in segment_id_set:
            continue

        segment_id_set.add(knowledge_source.get(segment_id))

        # 创建记录
        question = knowledge_source.get("question", "")
        answers = knowledge_source.get("answers", [])

        if not question:
            content = answers[0]['content']
        else:
            # TODO 没有考虑渠道字段
            content = f"Qestion: {question}\n\nAnswer: {answers[0]['content']}"

        title = json.dumps(knowledge_source, ensure_ascii=False)

        records.append(
            {
                "content": content,
                "score": round(float(score), 2),  # 四舍五入到两位小数
                "title": title,
                "metadata": knowledge_source,
            }
        )

    return {"records": records}

