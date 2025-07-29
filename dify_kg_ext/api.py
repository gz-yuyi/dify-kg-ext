import logging
import time
import uuid
from contextlib import asynccontextmanager

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
    cleanup,
    create_dataset_if_not_exists,
    download_file_from_url,
    get_document_chunks,
    get_document_status,
    parse_documents,
    upload_document_to_dataset,
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting Knowledge Database API...")
    yield
    # 关闭时
    logger.info("Shutting down Knowledge Database API...")
    await cleanup()


# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Database API",
    description="Knowledge Database with Dify External Knowledge API Integration",
    version="1.0.0",
    lifespan=lifespan,
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
    # 从文件路径提取文档名
    document_name = request.file_path.split("/")[-1]

    # 生成唯一的数据集名称
    dataset_name = f"dataset_{str(uuid.uuid4()).replace('-', '')}"

    # 创建数据集，获取RAGFlow返回的真实dataset_id
    dataset_id = await create_dataset_if_not_exists(dataset_name)

    # 处理文件路径（URL或本地文件）
    if request.file_path.startswith(("http://", "https://")):
        # 下载文件
        logger.info(f"Downloading file from URL: {request.file_path}")
        from pathlib import Path

        temp_path = Path(f"/tmp/{document_name}")
        temp_path.parent.mkdir(exist_ok=True)

        success = await download_file_from_url(request.file_path, temp_path)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download file from {request.file_path}",
            )

        file_content = temp_path.read_bytes()
        temp_path.unlink()  # 清理临时文件
        logger.info(f"Downloaded and processed file: {document_name}")
    else:
        # 本地文件
        logger.info(f"Processing local file: {request.file_path}")
        from pathlib import Path

        file_path_obj = Path(request.file_path)
        if not file_path_obj.exists():
            raise HTTPException(
                status_code=400, detail=f"File not found: {request.file_path}"
            )

        file_content = file_path_obj.read_bytes()
        logger.info(
            f"Read local file: {document_name}, size: {len(file_content)} bytes"
        )

    # 上传文档到RAGFlow（不等待解析完成），获取RAGFlow返回的真实document_id
    document_id = await upload_document_to_dataset(
        dataset_id, file_content, document_name
    )

    # 启动解析（不等待完成）
    await parse_documents(dataset_id, [document_id])

    # part_document_id设置为"part" + document_id
    part_document_id = "part" + document_id
    part_document_name = f"part_{document_name}"

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
    # 检查是否是part模式（document_id以"part"开头）
    is_part_mode = request.document_id.startswith("part")

    # 获取真实的RAGFlow document_id
    if is_part_mode:
        # 如果是part模式，从document_id中提取真实的document_id
        ragflow_document_id = request.document_id[4:]  # 去掉"part"前缀
    else:
        # 如果不是part模式，直接使用document_id
        ragflow_document_id = request.document_id

    # dataset_id现在已经是RAGFlow的真实ID，直接使用
    ragflow_dataset_id = request.dataset_id

    # 先检查文档解析状态
    doc_status = await get_document_status(ragflow_dataset_id, ragflow_document_id)
    if not doc_status:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": 2001,
                "error_msg": "Document not found or unable to get document status.",
            },
        )

    run_status = doc_status.get("run", "UNSTART")
    progress_msg = doc_status.get("progress_msg", "")

    # 根据解析状态决定返回内容
    if run_status in ["UNSTART", "RUNNING"]:
        # 正在解析中，返回提示信息
        status_message = f"Document is being parsed... Status: {run_status}"
        if progress_msg:
            status_message += f", Progress: {progress_msg}"

        return AnalyzingDocumentResponse(chunks=[status_message], sign=True)
    elif run_status == "FAIL":
        # 解析失败
        error_msg = progress_msg or "Document parsing failed"
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 3001,
                "error_msg": f"Document parsing failed: {error_msg}",
            },
        )
    elif run_status == "DONE":
        # 解析完成，获取chunks
        chunks = await get_document_chunks(
            ragflow_dataset_id, ragflow_document_id, is_part_mode
        )
        return AnalyzingDocumentResponse(chunks=chunks, sign=True)
    else:
        # 未知状态
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 3002,
                "error_msg": f"Unknown document parsing status: {run_status}",
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
    chunks = await chunk_text_directly(
        text=request.text,
        chunk_method=request.chunk_method,
        parser_config=parser_config,
    )

    return AnalyzingDocumentResponse(chunks=chunks, sign=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
