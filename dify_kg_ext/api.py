import logging
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from dify_kg_ext.dataclasses import (
    BaseResponse,
    BindBatchResponse,
    ErrorResponse,
    Knowledge,
    KnowledgeBindBatchRequest,
    KnowledgeDeleteRequest,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeUnbindBatchRequest,
    Record,
    RetrievalRequest,
    RetrievalResponse,
    UnbindBatchResponse,
)
from dify_kg_ext.dataclasses.doc_parse import (
    AnalyzingDocumentRequest,
    AnalyzingDocumentResponse,
    TextChunkingRequest,
    UploadDocumentRequest,
    UploadDocumentResponse,
)
from dify_kg_ext.es import (
    bind_knowledge_to_library,
    check_knowledge_exists,
    delete_documents,
    index_document,
    retrieve_knowledge,
    search_knowledge,
    unbind_knowledge_from_library,
)
from dify_kg_ext.ragflow_service import (
    chunk_text_directly,
    upload_and_parse_document,
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 简化的文档缓存，用于存储RAGFlow返回的结果
document_cache = {}

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Database API",
    description="Knowledge Database with Dify External Knowledge API Integration",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(authorization: str = Header(None)):
    """验证API密钥"""
    if not authorization:
        raise HTTPException(status_code=403, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Invalid authorization format")

    token = authorization.replace("Bearer ", "")
    if len(token) < 10:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return token


@app.get("/")
async def root():
    """
    服务信息和可用端点
    """
    return {
        "service": "Knowledge Database API",
        "version": "1.0.0",
        "features": [
            "Knowledge Management (CRUD)",
            "Document Processing with RAGFlow",
            "Text Chunking",
            "Dify External Knowledge API",
            "Semantic Search & Vector Retrieval",
        ],
        "endpoints": {
            "knowledge_management": [
                "POST /knowledge/update - Add/Update knowledge",
                "POST /knowledge/search - Search knowledge",
                "POST /knowledge/delete - Delete knowledge",
                "POST /knowledge/bind_batch - Bind knowledge to library",
                "POST /knowledge/unbind_batch - Unbind knowledge from library",
            ],
            "document_processing": [
                "POST /upload_documents - Upload and process documents",
                "POST /analyzing_documents - Get document chunks",
                "POST /chunk_text - Direct text chunking",
            ],
            "dify_integration": ["POST /retrieval - Dify External Knowledge API"],
            "system": [
                "GET / - Service information",
                "GET /health - Health check",
                "GET /docs - API documentation",
            ],
        },
        "documentation": "/docs",
        "health_check": "/health",
    }


@app.get("/health")
async def health_check():
    """
    健康检查
    """
    return {"status": "healthy", "timestamp": time.time()}


@app.post("/knowledge/update", response_model=BaseResponse)
async def update_knowledge(knowledge: Knowledge):
    """
    添加或更新知识条目
    """
    segment_id = await index_document(knowledge)
    if not segment_id:
        raise HTTPException(status_code=500, detail="Failed to index document")

    return {"code": 200, "msg": "success"}


@app.post("/knowledge/delete", response_model=BaseResponse)
async def delete_knowledge(request: KnowledgeDeleteRequest):
    """
    删除知识条目
    """
    result = await delete_documents(request.segment_ids)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete documents")

    return {"code": 200, "msg": "success"}


@app.post("/knowledge/bind_batch", response_model=BindBatchResponse)
async def bind_knowledge_batch(request: KnowledgeBindBatchRequest):
    """
    批量绑定知识到知识库
    """
    result = await bind_knowledge_to_library(request.library_id, request.category_ids)
    if not result or result.get("success_count", 0) == 0:
        raise HTTPException(status_code=500, detail="Failed to bind knowledge")

    return {
        "code": 200,
        "msg": "success",
        "data": {
            "success_count": result.get("success_count", 0),
            "failed_ids": result.get("failed_ids", []),
        },
    }


@app.post("/knowledge/unbind_batch", response_model=UnbindBatchResponse)
async def unbind_knowledge_batch(request: KnowledgeUnbindBatchRequest):
    """
    批量解绑知识从知识库
    """
    result = await unbind_knowledge_from_library(
        request.library_id, request.category_ids, request.delete_type
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to unbind knowledge")

    return {
        "code": 200,
        "msg": "success",
        "data": {
            "success_count": result.get("success_count", 0),
            "failed_ids": result.get("failed_ids", []),
        },
    }


@app.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(request: KnowledgeSearchRequest):
    """
    搜索知识条目
    """
    result = await search_knowledge(
        query=request.query, library_id=request.library_id, limit=request.limit
    )

    # Convert Pydantic objects to dictionaries for serialization
    segments_dict = [segment.model_dump() for segment in result["segments"]]

    return {"code": 200, "msg": "success", "data": {"segments": segments_dict}}


@app.post(
    "/retrieval",
    response_model=RetrievalResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Authorization failed"},
        404: {"model": ErrorResponse, "description": "Knowledge base not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def retrieval(request: RetrievalRequest, api_key: str = Depends(verify_api_key)):
    """
    Dify External Knowledge API - 从外部知识库检索数据

    这个接口完全兼容Dify平台的External Knowledge API规范。
    Dify会调用这个接口来从外部知识库检索相关信息。

    同时也可以作为通用的知识检索接口使用。

    请求格式符合Dify标准：
    - knowledge_id: 知识库唯一标识符
    - query: 用户查询文本
    - retrieval_setting: 检索配置参数
      - top_k: 返回结果的最大数量
      - score_threshold: 相关性分数阈值
    - metadata_condition: 可选的元数据过滤条件

    响应格式符合Dify标准：
    - records: 检索结果列表
      - content: 文档内容
      - score: 相关性分数 (0-1)
      - title: 文档标题
      - metadata: 文档元数据
    """
    # 记录请求信息用于调试
    logger.info(
        f"Knowledge retrieval request: knowledge_id={request.knowledge_id}, "
        f"query='{request.query}', top_k={request.retrieval_setting.top_k}"
    )

    # 检查知识库是否存在
    if not await check_knowledge_exists(request.knowledge_id):
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": 2001,
                "error_msg": "The knowledge base does not exist",
            },
        )

    # 从外部知识库检索数据
    result = await retrieve_knowledge(
        knowledge_id=request.knowledge_id,
        query=request.query,
        top_k=request.retrieval_setting.top_k,
        score_threshold=request.retrieval_setting.score_threshold,
        metadata_condition=request.metadata_condition,
    )

    # 转换为Dify格式的响应
    records = []
    for record_data in result.get("records", []):
        # 构造符合Dify规范的记录对象
        record = Record(
            content=record_data.get("content", ""),
            score=record_data.get("score", 0.0),
            title=record_data.get("title", ""),
            metadata=record_data.get("metadata", {}),
        )
        records.append(record)

    logger.info(f"Retrieved {len(records)} records for query: '{request.query}'")

    return RetrievalResponse(records=records)


@app.post("/upload_documents", response_model=UploadDocumentResponse)
async def upload_document(request: UploadDocumentRequest):
    """
    上传文档并使用RAGFlow进行处理
    """
    # 生成唯一ID
    dataset_id = str(uuid.uuid4()).replace("-", "")
    document_id = str(uuid.uuid4()).replace("-", "")
    part_document_id = str(uuid.uuid4()).replace("-", "")

    # 从文件路径提取文档名
    document_name = request.file_path.split("/")[-1]
    part_document_name = f"part_{document_name}"

    # 使用RAGFlow处理文档
    result = upload_and_parse_document(
        file_path=request.file_path,
        dataset_name=f"dataset_{dataset_id}",
        chunk_method="naive",  # 默认使用naive方法
    )

    # 缓存结果
    document_cache[document_id] = {
        "dataset_id": result["dataset_id"],
        "document_id": result["document_id"],
        "chunks": result["chunks"],
        "status": "completed",
    }

    # 创建部分结果（前10个分块）
    partial_chunks = (
        result["chunks"][:10] if len(result["chunks"]) > 10 else result["chunks"]
    )
    document_cache[part_document_id] = {
        "dataset_id": result["dataset_id"],
        "document_id": result["document_id"],
        "chunks": partial_chunks,
        "status": "completed",
    }

    return UploadDocumentResponse(
        dataset_id=dataset_id,
        document_id=document_id,
        document_name=document_name,
        part_document_id=part_document_id,
        part_document_name=part_document_name,
        sign=True,
    )


@app.post("/analyzing_documents", response_model=AnalyzingDocumentResponse)
async def analyzing_document(request: AnalyzingDocumentRequest):
    """
    使用RAGFlow分析文档并返回分块结果
    """
    # 检查缓存中是否有结果
    if request.document_id in document_cache:
        cached_result = document_cache[request.document_id]
        return AnalyzingDocumentResponse(chunks=cached_result["chunks"], sign=True)

    # 如果缓存中没有，暂时返回错误，提示需要先上传文档
    raise HTTPException(
        status_code=404,
        detail={
            "error_code": 2001,
            "error_msg": "Document not found. Please upload the document first.",
        },
    )


@app.post("/chunk_text", response_model=AnalyzingDocumentResponse)
async def chunk_text(request: TextChunkingRequest):
    """
    直接对文本进行分片处理，使用RAGFlow
    """
    # 构建parser_config
    parser_config = request.parser_config if request.parser_flag == 1 else None

    # 使用RAGFlow进行文本分块
    chunks = chunk_text_directly(
        text=request.text,
        chunk_method=request.chunk_method,
        parser_config=parser_config,
    )

    return AnalyzingDocumentResponse(chunks=chunks, sign=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
