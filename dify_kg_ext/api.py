import logging
import uuid

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
    UploadDocumentRequest,
    UploadDocumentResponse,
    TextChunkingRequest,
)
from dify_kg_ext.worker import parse_document_task
from dify_kg_ext.es import (
    bind_knowledge_to_library,
    check_knowledge_exists,
    delete_documents,
    index_document,
    retrieve_knowledge,
    search_knowledge,
    unbind_knowledge_from_library,
)
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from tempfile import NamedTemporaryFile
import os
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Knowledge Database API",
    description="Knowledge Database Management API with Dify External Knowledge API support",
    version="1.0.0",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    自定义HTTP异常处理器，确保错误响应格式符合Dify标准
    """
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # 如果不是标准格式，转换为标准格式
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.status_code, "error_msg": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    通用异常处理器
    """
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error_code": 5001, "error_msg": f"Internal server error: {str(exc)}"},
    )


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
    删除指定的知识条目
    """
    await delete_documents(request.segment_ids)
    return {"code": 200, "msg": "success"}


@app.post("/knowledge/bind_batch", response_model=BindBatchResponse)
async def bind_knowledge_batch(request: KnowledgeBindBatchRequest):
    """
    批量绑定知识条目到指定库
    """
    result = await bind_knowledge_to_library(
        library_id=request.library_id, category_ids=request.category_ids
    )

    return {"code": 200, "msg": "success", "data": result}


@app.post("/knowledge/unbind_batch", response_model=UnbindBatchResponse)
async def unbind_knowledge_batch(request: KnowledgeUnbindBatchRequest):
    """
    解除知识条目与指定库的绑定
    """
    result = await unbind_knowledge_from_library(
        library_id=request.library_id,
        category_ids=request.category_ids,
        delete_type=request.delete_type,
    )

    return {"code": 200, "msg": "success", "data": result}


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


# 验证API密钥的函数 - 支持更灵活的验证
async def verify_api_key(authorization: str = Header(None)):
    """
    验证API密钥 - 兼容Dify和内部使用
    """
    if not authorization:
        raise HTTPException(
            status_code=403,
            detail={"error_code": 1001, "error_msg": "Missing Authorization header"},
        )

    if " " not in authorization:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": 1001,
                "error_msg": "Invalid Authorization header format. Expected 'Bearer <api-key>' format.",
            },
        )

    auth_scheme, auth_token = authorization.split(None, 1)
    auth_scheme = auth_scheme.lower()

    if auth_scheme != "bearer":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": 1001,
                "error_msg": "Invalid Authorization header format. Expected 'Bearer <api-key>' format.",
            },
        )

    # 支持多种API密钥格式
    # 1. 原有的固定密钥（向后兼容）
    # 2. Dify使用的任意长度超过10位的密钥
    if auth_token == "your-api-key" or len(auth_token) >= 10:
        return auth_token

    raise HTTPException(
        status_code=403,
        detail={"error_code": 1002, "error_msg": "Authorization failed"},
    )


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

    # 调用核心检索逻辑
    result = await retrieve_knowledge(
        knowledge_id=request.knowledge_id,
        query=request.query,
        top_k=request.retrieval_setting.top_k,
        score_threshold=request.retrieval_setting.score_threshold,
        metadata_condition=request.metadata_condition,
    )

    # 确保返回的格式符合Dify标准
    records = []
    for record_data in result["records"]:
        record = Record(
            content=record_data["content"],
            score=record_data["score"],
            title=record_data["title"] if record_data["title"] else "",
            metadata=record_data.get("metadata", {}),
        )
        records.append(record)

    response = RetrievalResponse(records=records)

    logger.info(f"Knowledge retrieval response: returned {len(records)} records")
    return response


@app.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return {
        "status": "healthy",
        "service": "knowledge-database-api",
        "features": ["knowledge-management", "dify-external-knowledge-api"],
    }


@app.get("/")
async def root():
    """
    API服务信息
    """
    return {
        "service": "Knowledge Database API",
        "version": "1.0.0",
        "description": "Knowledge Database Management API with Dify External Knowledge API support",
        "features": {
            "knowledge_management": "Complete CRUD operations for knowledge base",
            "dify_integration": "Dify-compatible External Knowledge API",
            "semantic_search": "Vector-based semantic search with Elasticsearch",
        },
        "endpoints": {
            "knowledge_management": {
                "update": "POST /knowledge/update - Add or update knowledge",
                "delete": "POST /knowledge/delete - Delete knowledge entries",
                "bind": "POST /knowledge/bind_batch - Bind knowledge to library",
                "unbind": "POST /knowledge/unbind_batch - Unbind knowledge from library",
                "search": "POST /knowledge/search - Search knowledge entries",
            },
            "dify_integration": {
                "retrieval": "POST /retrieval - Knowledge retrieval for Dify platform"
            },
            "system": {
                "health": "GET /health - Health check",
                "info": "GET / - Service information",
                "docs": "GET /docs - API documentation",
            },
        },
    }


@app.post("/upload_document", response_model=UploadDocumentResponse)
async def upload_document(request: UploadDocumentRequest):
    """
    上传文档并返回文档ID
    """
    # 生成唯一ID
    dataset_id = str(uuid.uuid4()).replace("-", "")
    document_id = str(uuid.uuid4()).replace("-", "")
    part_document_id = str(uuid.uuid4()).replace("-", "")

    # 从文件路径提取文档名
    document_name = request.file_path.split("/")[-1]
    part_document_name = f"part_{document_name}"

    return UploadDocumentResponse(
        dataset_id=dataset_id,
        document_id=document_id,
        document_name=document_name,
        part_document_id=part_document_id,
        part_document_name=part_document_name,
        sign=True,
    )


@app.post("/analyzing_document", response_model=AnalyzingDocumentResponse)
async def analyzing_document(request: AnalyzingDocumentRequest):
    """
    解析文档并返回分块结果
    """
    # 构建解析参数
    parse_kwargs = {}

    if request.parser_flag == 1 and request.parser_config:
        # 使用自定义解析配置
        if "chunk_token_count" in request.parser_config:
            parse_kwargs["max_tokens"] = request.parser_config["chunk_token_count"]
        if "task_page_size" in request.parser_config:
            parse_kwargs["max_num_pages"] = request.parser_config["task_page_size"]

    # 这里需要根据document_id获取实际的文件路径
    # 在实际应用中，应该从数据库或存储中获取文件路径
    file_path = f"/tmp/{request.document_name}"  # 示例路径

    try:
        # 调用Celery任务进行文档解析
        task_result = parse_document_task.delay(file_path, **parse_kwargs)

        # 等待任务完成并获取结果
        chunks_data = task_result.get(timeout=300)  # 5分钟超时

        # 提取文本内容
        chunks = []
        for chunk in chunks_data:
            if isinstance(chunk, dict) and "text" in chunk:
                chunks.append(chunk["text"])
            elif hasattr(chunk, "text"):  # Handle chunk objects
                chunks.append(chunk.text)
            else:
                chunks.append(str(chunk))

        return AnalyzingDocumentResponse(chunks=chunks, sign=True)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 5001,
                "error_msg": f"Document parsing failed: {str(e)}",
            },
        )


@app.post("/chunk_text", response_model=AnalyzingDocumentResponse)
async def chunk_text(request: TextChunkingRequest):
    """
    直接对文本进行分片处理
    """
    # 创建临时文件保存文本
    with NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as temp_file:
        temp_file.write(request.text)
        temp_file.flush()  # Ensure content is written to disk
        temp_file_path = temp_file.name
    
    # 构建解析参数
    parse_kwargs = {}
    if request.parser_flag == 1 and request.parser_config:
        if "chunk_token_count" in request.parser_config:
            parse_kwargs["max_tokens"] = request.parser_config["chunk_token_count"]
        if "task_page_size" in request.parser_config:
            parse_kwargs["max_num_pages"] = request.parser_config["task_page_size"]

    try:
        # 调用Celery任务进行文本解析
        task_result = parse_document_task.delay(temp_file_path, **parse_kwargs)
        chunks_data = task_result.get(timeout=300)  # 5分钟超时

        # 提取文本内容
        chunks = []
        for chunk in chunks_data:
            if isinstance(chunk, dict) and "text" in chunk:
                chunks.append(chunk["text"])
            elif hasattr(chunk, "text"):  # Handle chunk objects
                chunks.append(chunk.text)
            else:
                chunks.append(str(chunk))

        return AnalyzingDocumentResponse(chunks=chunks, sign=True)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 5001,
                "error_msg": f"Text chunking failed: {str(e)}",
            },
        )
    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
