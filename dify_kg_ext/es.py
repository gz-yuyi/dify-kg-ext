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
        }
    }
}

# Main knowledge data mapping with segment_id as primary key
knowledge_mapping = {
    "mappings": {
        "_id": {"path": "segment_id"},  # Using segment_id as document ID
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
            "library_ids": {"type": "keyword"},  # Added field for multiple libraries
        },
    }
}

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
es_client = elasticsearch.AsyncElasticsearch(
    [ES_HOST], basic_auth=("elastic", "telecom12345")
)


async def index_document(doc: "Knowledge"):
    """Index a knowledge document using bulk operations for better atomicity"""
    # First delete all vectors associated with this segment_id
    delete_query = {"query": {"term": {"segment_id": doc.segment_id}}}
    await es_client.delete_by_query(
        index=VECTOR_INDEX, body=delete_query, ignore=[404]
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
        "library_ids": doc.library_ids if hasattr(doc, "library_ids") else [],
    }

    # Index operation for knowledge document
    bulk_operations.append({
        "index": {
            "_index": KNOWLEDGE_INDEX,
            "_id": doc.segment_id
        }
    })
    bulk_operations.append(knowledge_doc)

    # Add question vector document operation
    if question_vector:
        question_vector_doc = {
            "segment_id": doc.segment_id,
            "vector_type": "question",
            "vector": question_vector,
            "text": doc.question,
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
        }
        bulk_operations.append({"index": {"_index": VECTOR_INDEX}})
        bulk_operations.append(answer_vector_doc)

    # Execute all operations in a single bulk request
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)

    return doc.segment_id

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
    search_query = {
        "query": {
            "terms": {
                "segment_id": segment_ids
            }
        },
        "size": 10000,  # Adjust as needed based on your data volume
        "_source": False  # We only need the IDs
    }
    
    vector_results = await es_client.search(
        index=VECTOR_INDEX,
        body=search_query
    )
    
    # Prepare bulk delete operations for both knowledge and vector documents
    bulk_operations = []
    
    # Add knowledge document deletions
    for segment_id in segment_ids:
        bulk_operations.append({
            "delete": {
                "_index": KNOWLEDGE_INDEX,
                "_id": segment_id
            }
        })
    
    # Add vector document deletions
    for hit in vector_results["hits"]["hits"]:
        bulk_operations.append({
            "delete": {
                "_index": VECTOR_INDEX,
                "_id": hit["_id"]
            }
        })
    
    # Execute bulk delete for all documents in a single operation
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)

# Add bind and unbind functions
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
    
    success_count = 0
    failed_ids = []
    bulk_operations = []
    
    # First collect all documents that exist
    for category_id in category_ids:
        exists = await es_client.exists(index=KNOWLEDGE_INDEX, id=category_id)
        if not exists:
            failed_ids.append(category_id)
            continue
            
        doc = await es_client.get(index=KNOWLEDGE_INDEX, id=category_id, ignore=[404])
        if "_source" not in doc:
            failed_ids.append(category_id)
            continue
            
        source = doc["_source"]
        library_ids = source.get("library_ids", [])
        
        # Only update if library_id is not already in the list
        if library_id not in library_ids:
            library_ids.append(library_id)
            bulk_operations.append({
                "update": {
                    "_index": KNOWLEDGE_INDEX,
                    "_id": category_id
                }
            })
            bulk_operations.append({
                "doc": {
                    "library_ids": library_ids
                }
            })
            success_count += 1
    
    # Execute bulk update if we have operations
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)
    
    return {"success_count": success_count, "failed_ids": failed_ids}

async def unbind_knowledge_from_library(library_id: str, category_ids: List[str], delete_type: str = "part"):
    """
    Unbind knowledge documents from a library
    
    Args:
        library_id: The library ID to unbind from
        category_ids: List of category IDs to unbind (used when delete_type is "part")
        delete_type: "all" to unbind all documents from library, "part" to unbind only specified category_ids
        
    Returns:
        Dict with success_count and failed_ids
    """
    if not library_id:
        return {"success_count": 0, "failed_ids": category_ids or []}
    
    success_count = 0
    failed_ids = []
    bulk_operations = []
    
    if delete_type == "all":
        # Find all documents with this library_id
        search_query = {
            "query": {
                "term": {
                    "library_ids": library_id
                }
            },
            "size": 10000
        }
        
        results = await es_client.search(
            index=KNOWLEDGE_INDEX,
            body=search_query,
            _source=["segment_id", "library_ids"]
        )
        
        # Update each document to remove the library_id
        for hit in results["hits"]["hits"]:
            doc_id = hit["_id"]
            library_ids = hit["_source"].get("library_ids", [])
            if library_id in library_ids:
                library_ids.remove(library_id)
                bulk_operations.append({
                    "update": {
                        "_index": KNOWLEDGE_INDEX,
                        "_id": doc_id
                    }
                })
                bulk_operations.append({
                    "doc": {
                        "library_ids": library_ids
                    }
                })
        
        if bulk_operations:
            await es_client.bulk(operations=bulk_operations, refresh=True)
            success_count = len(bulk_operations) // 2  # Each update is 2 operations
    else:
        # Process only specified category_ids
        for category_id in category_ids:
            exists = await es_client.exists(index=KNOWLEDGE_INDEX, id=category_id)
            if not exists:
                failed_ids.append(category_id)
                continue
                
            doc = await es_client.get(index=KNOWLEDGE_INDEX, id=category_id, ignore=[404])
            if "_source" not in doc:
                failed_ids.append(category_id)
                continue
                
            source = doc["_source"]
            library_ids = source.get("library_ids", [])
            
            # Only update if library_id is in the list
            if library_id in library_ids:
                library_ids.remove(library_id)
                bulk_operations.append({
                    "update": {
                        "_index": KNOWLEDGE_INDEX,
                        "_id": category_id
                    }
                })
                bulk_operations.append({
                    "doc": {
                        "library_ids": library_ids
                    }
                })
                success_count += 1
    
    # Execute bulk update if we have operations
    if bulk_operations:
        await es_client.bulk(operations=bulk_operations, refresh=True)
    
    return {"success_count": success_count, "failed_ids": failed_ids}