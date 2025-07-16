import io
import json
import logging
import os
import time
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

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
from dify_kg_ext.worker import chunk_document_task, parse_document_task

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for local storage
LOCAL_FILES_DIR = Path("local_files")
CHUNKS_SUBDIR = "chunks"
PARTIAL_CHUNKS_SUBDIR = "partial_chunks"


def ensure_storage_structure():
    """确保存储目录结构存在"""
    chunks_dir = LOCAL_FILES_DIR / CHUNKS_SUBDIR
    partial_chunks_dir = LOCAL_FILES_DIR / PARTIAL_CHUNKS_SUBDIR

    chunks_dir.mkdir(parents=True, exist_ok=True)
    partial_chunks_dir.mkdir(parents=True, exist_ok=True)


def get_document_storage_path(document_id: str, partial: bool = False) -> Path:
    """获取文档存储路径"""
    subdir = PARTIAL_CHUNKS_SUBDIR if partial else CHUNKS_SUBDIR
    return LOCAL_FILES_DIR / subdir / f"{document_id}.json"


async def download_file_from_url(url: str, destination: Path) -> bool:
    """从URL下载文件到本地路径"""
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)
            return True
    except Exception as e:
        logger.error(f"Failed to download file from {url}: {e}")
        return False


async def process_document_async(
    document_id: str, part_document_id: str, file_path: str, parser_config: dict = None
):
    """异步处理文档并保存解析结果"""
    try:
        # 确保存储目录存在
        ensure_storage_structure()

        # 提取文件扩展名
        file_extension = Path(file_path).suffix.lower()
        if not file_extension:
            # 如果无法确定扩展名，尝试从URL内容类型检测
            file_extension = ".pdf"  # 默认使用PDF

        # 下载文件到临时位置，保持原始扩展名
        temp_file = LOCAL_FILES_DIR / "temp" / f"{document_id}_temp{file_extension}"
        temp_file.parent.mkdir(parents=True, exist_ok=True)

        if file_path.startswith(("http://", "https://")):
            success = await download_file_from_url(file_path, temp_file)
            if not success:
                raise Exception("Failed to download file")
        else:
            # 本地文件，直接复制
            import shutil

            shutil.copy2(file_path, temp_file)

        # 构建解析参数
        parse_kwargs = {}
        if parser_config:
            if "task_page_size" in parser_config:
                parse_kwargs["max_num_pages"] = parser_config["task_page_size"]

        # 调用Celery任务进行文档解析
        task_result = parse_document_task.delay(str(temp_file), **parse_kwargs)
        document_json = task_result.get(timeout=300)  # 5分钟超时

        # 保存解析后的文档（不立即分块）
        full_result_path = get_document_storage_path(document_id, partial=False)
        with open(full_result_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "document_id": document_id,
                    "document_json": document_json,
                    "file_path": file_path,
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "parsed",
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        # 保存部分结果（解析后的文档，用于快速展示）
        partial_result_path = get_document_storage_path(part_document_id, partial=True)
        with open(partial_result_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "document_id": part_document_id,
                    "document_json": document_json,
                    "file_path": file_path,
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "parsed",
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()

        logger.info(f"Document parsing completed: {document_id}")

    except Exception as e:
        logger.error(f"Document parsing failed for {document_id}: {e}")
        # 保存错误状态
        error_result = {"document_id": document_id, "error": str(e), "status": "failed"}

        full_result_path = get_document_storage_path(document_id, partial=False)
        with open(full_result_path, "w", encoding="utf-8") as f:
            json.dump(error_result, f, indent=2)

        partial_result_path = get_document_storage_path(part_document_id, partial=True)
        with open(partial_result_path, "w", encoding="utf-8") as f:
            json.dump(error_result, f, indent=2)


def load_document_chunks(
    document_id: str, partial: bool = False, chunk_config: dict = None
) -> list:
    """从存储中加载文档分块结果，如果没有分块则执行分块操作"""
    storage_path = get_document_storage_path(document_id, partial=partial)
    chunks_storage_path = get_document_storage_path(
        f"{document_id}_chunks", partial=partial
    )

    if not storage_path.exists():
        raise FileNotFoundError(f"Document {document_id} not found")

    # 首先检查是否已经分块
    if chunks_storage_path.exists():
        with open(chunks_storage_path, "r", encoding="utf-8") as f:
            result = json.load(f)

        if result.get("status") == "failed":
            raise Exception(result.get("error", "Document chunking failed"))

        return result.get("chunks", [])

    # 如果还没有分块，执行分块操作
    try:
        with open(storage_path, "r", encoding="utf-8") as f:
            parse_result = json.load(f)

        if parse_result.get("status") == "failed":
            raise Exception(parse_result.get("error", "Document parsing failed"))
        if parse_result.get("status") != "parsed":
            raise Exception("Document not yet parsed")

        # 从存储中重建文档对象

        document_json = parse_result["document_json"]

        # 构建分块参数
        chunk_kwargs = {}
        if chunk_config:
            if "chunk_token_count" in chunk_config:
                chunk_kwargs["max_tokens"] = chunk_config["chunk_token_count"]
        else:
            chunk_kwargs["max_tokens"] = 1024  # 默认分块大小

        # 执行分块操作
        try:
            chunks = chunk_document_task(document_json, **chunk_kwargs)

            # 提取文本内容
            text_chunks = []
            for chunk in chunks:
                if isinstance(chunk, dict) and "text" in chunk:
                    text_chunks.append(chunk["text"])
                elif hasattr(chunk, "text"):
                    text_chunks.append(chunk.text)
                else:
                    text_chunks.append(str(chunk))

            # 保存分块结果
            result = {
                "document_id": document_id,
                "chunks": text_chunks,
                "total_chunks": len(text_chunks),
                "chunk_config": chunk_kwargs,
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed",
            }

            # 保存完整分块结果
            with open(chunks_storage_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            # 保存部分分块结果（用于快速展示）
            partial_chunks_storage_path = get_document_storage_path(
                f"{document_id}_chunks", partial=True
            )
            partial_text_chunks = (
                text_chunks[:10] if len(text_chunks) > 10 else text_chunks
            )
            partial_result = {
                "document_id": document_id,
                "chunks": partial_text_chunks,
                "total_chunks": len(text_chunks),
                "displayed_chunks": len(partial_text_chunks),
                "chunk_config": chunk_kwargs,
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed",
            }

            with open(partial_chunks_storage_path, "w", encoding="utf-8") as f:
                json.dump(partial_result, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Document chunking completed: {document_id} ({len(text_chunks)} chunks)"
            )

            if partial:
                return partial_text_chunks
            else:
                return text_chunks

        except Exception as e:
            logger.error(f"Document chunking failed for {document_id}: {e}")
            # 保存错误状态
            error_result = {
                "document_id": document_id,
                "error": str(e),
                "status": "failed",
            }

            with open(chunks_storage_path, "w", encoding="utf-8") as f:
                json.dump(error_result, f, indent=2)

            raise Exception(f"Document chunking failed: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to load or chunk document {document_id}: {e}")
        raise


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


@app.post("/upload_documents", response_model=UploadDocumentResponse)
async def upload_document(
    request: UploadDocumentRequest, background_tasks: BackgroundTasks
):
    """
    上传文档并立即触发后台解析任务
    """
    # 生成唯一ID
    dataset_id = str(uuid.uuid4()).replace("-", "")
    document_id = str(uuid.uuid4()).replace("-", "")
    part_document_id = str(uuid.uuid4()).replace("-", "")

    # 从文件路径提取文档名
    document_name = request.file_path.split("/")[-1]
    part_document_name = f"part_{document_name}"

    # 立即触发后台处理任务
    background_tasks.add_task(
        process_document_async,
        document_id,
        part_document_id,
        request.file_path,
        {},  # 默认解析配置
    )

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
    从存储中读取已解析的文档并执行分块操作
    """
    try:
        # 检查请求是否使用part_document_id进行快速展示
        use_partial = (
            "part" in request.document_name.lower()
            or "part" in str(request.document_id).lower()
        )
        target_document_id = request.document_id

        # 构建分块配置
        chunk_config = {}
        if request.parser_config:
            chunk_config.update(request.parser_config)

        # 从存储中加载文档并执行分块操作
        chunks = load_document_chunks(
            target_document_id, partial=use_partial, chunk_config=chunk_config
        )

        if not chunks:
            raise Exception("No chunks found for document")

        return AnalyzingDocumentResponse(chunks=chunks, sign=True)

    except FileNotFoundError as e:
        # 文档不存在或尚未处理完成
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": 2001,
                "error_msg": str(e),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 5001,
                "error_msg": f"Failed to load document chunks: {str(e)}",
            },
        )


@app.post("/chunk_text", response_model=AnalyzingDocumentResponse)
async def chunk_text(request: TextChunkingRequest):
    """
    直接对文本进行分片处理，使用新的存储系统
    """
    # 生成临时文档ID
    document_id = str(uuid.uuid4()).replace("-", "")

    # 创建临时文件保存文本
    with NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as temp_file:
        temp_file.write(request.text)
        temp_file.flush()  # Ensure content is written to disk
        temp_file_path = temp_file.name

    # 构建解析参数
    parse_kwargs = {}
    parser_config = {}
    if request.parser_flag == 1 and request.parser_config:
        parser_config = request.parser_config
        if "task_page_size" in request.parser_config:
            parse_kwargs["max_num_pages"] = request.parser_config["task_page_size"]

    try:
        # 创建文档处理任务 - 先解析文档
        await process_document_async(
            document_id,
            document_id,  # 文本分块不需要partial_id，使用相同的id
            temp_file_path,
            parser_config,
        )

        # 然后执行分块操作
        chunks = load_document_chunks(
            document_id, partial=False, chunk_config=parser_config
        )

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
