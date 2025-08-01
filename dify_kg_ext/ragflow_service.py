import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import aiohttp
from aiofiles import open as aio_open


logger = logging.getLogger(__name__)

# RAGFlow配置
RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "ragflow-test-key-12345")
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")

# 全局HTTP客户端session
_http_session: aiohttp.ClientSession | None = None


async def get_http_session() -> aiohttp.ClientSession:
    """获取HTTP客户端session"""
    global _http_session
    if _http_session is None or _http_session.closed:
        headers = {
            "Authorization": f"Bearer {RAGFLOW_API_KEY}",
            "Content-Type": "application/json",
        }
        _http_session = aiohttp.ClientSession(
            base_url=RAGFLOW_BASE_URL,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=300),  # 5分钟超时
        )
    return _http_session


async def close_http_session():
    """关闭HTTP客户端session"""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None


async def download_file_from_url(url: str, target_path: Path) -> bool:
    """从URL下载文件到本地路径"""
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        if response.status == 200:
            async with aio_open(target_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
            return True
        else:
            logger.error(f"Failed to download file from {url}: {response.status}")
            return False


async def create_dataset_if_not_exists(name: str) -> str | None:
    """创建数据集（如果不存在）并返回数据集ID"""
    session = await get_http_session()

    # 先尝试获取已存在的数据集
    logger.info(f"Searching for existing dataset: {name}")
    existing_dataset_id = await find_dataset_by_name(name)
    if existing_dataset_id:
        logger.info(f"Found existing dataset {name} with ID: {existing_dataset_id}")
        return existing_dataset_id

    # 创建新数据集
    logger.info(f"Creating new dataset: {name}")
    create_data = {"name": name}
    async with session.post("/api/v1/datasets", json=create_data) as response:
        if response.status == 200:
            result = await response.json()
            dataset_id = result.get("data", {}).get("id")
            if dataset_id:
                logger.info(f"Dataset created successfully with ID: {dataset_id}")
                return dataset_id
            else:
                logger.error(f"Dataset creation response did not contain ID: {result}")
                return None
        else:
            error_text = await response.text()
            logger.error(
                f"Failed to create dataset {name}: {response.status}, {error_text}"
            )
            return None


async def find_dataset_by_name(name: str) -> str | None:
    """根据名称查找数据集ID"""
    session = await get_http_session()

    # URL编码数据集名称以处理特殊字符
    from urllib.parse import quote

    encoded_name = quote(name)

    async with session.get(f"/api/v1/datasets?name={encoded_name}") as response:
        if response.status == 200:
            result = await response.json()
            datasets = result.get("data", [])
            if datasets and isinstance(datasets, list):
                logger.info(f"Found {len(datasets)} datasets matching name '{name}'")
                return datasets[0].get("id")
        else:
            error_text = await response.text()
            logger.warning(
                f"Failed to search datasets: {response.status}, {error_text}"
            )
        return None


async def upload_document_to_dataset(
    dataset_id: str, file_content: bytes, file_name: str
) -> str | None:
    """上传文档到数据集"""
    # 创建专用的multipart上传session，避免Content-Type冲突
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}

    async with aiohttp.ClientSession(
        base_url=RAGFLOW_BASE_URL,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=300),
    ) as session:
        form_data = aiohttp.FormData()
        form_data.add_field("file", file_content, filename=file_name)

        logger.info(f"Uploading document {file_name} to dataset {dataset_id}")

        async with session.post(
            f"/api/v1/datasets/{dataset_id}/documents", data=form_data
        ) as response:
            if response.status == 200:
                result = await response.json()
                documents = result.get("data", [])
                if documents:
                    document_id = documents[0].get("id")
                    logger.info(
                        f"Document uploaded successfully with ID: {document_id}"
                    )
                    return document_id
                else:
                    logger.error("Upload response did not contain document data")
            else:
                error_text = await response.text()
                logger.error(
                    f"Failed to upload document: {response.status}, {error_text}"
                )
            return None


async def update_document_config(
    dataset_id: str,
    document_id: str,
    chunk_method: str = "naive",
    parser_config: dict[str, Any] | None = None,
) -> bool:
    """更新文档配置"""
    session = await get_http_session()

    update_data = {"chunk_method": chunk_method}

    if parser_config:
        # 构建RAGFlow兼容的parser_config
        ragflow_parser_config = {}
        if "chunk_token_count" in parser_config:
            ragflow_parser_config["chunk_token_count"] = parser_config[
                "chunk_token_count"
            ]
        if "delimiter" in parser_config:
            ragflow_parser_config["delimiter"] = parser_config["delimiter"]
        if "layout_recognize" in parser_config:
            ragflow_parser_config["layout_recognize"] = parser_config[
                "layout_recognize"
            ]

        # 根据chunk_method添加默认配置
        if chunk_method == "naive":
            ragflow_parser_config.update(
                {
                    "chunk_token_count": ragflow_parser_config.get(
                        "chunk_token_count", 128
                    ),
                    "delimiter": ragflow_parser_config.get("delimiter", "\n"),
                    "html4excel": False,
                    "layout_recognize": ragflow_parser_config.get(
                        "layout_recognize", True
                    ),
                }
            )

        if ragflow_parser_config:
            update_data["parser_config"] = ragflow_parser_config

    logger.info(f"Updating document {document_id} config: {update_data}")

    async with session.put(
        f"/api/v1/datasets/{dataset_id}/documents/{document_id}", json=update_data
    ) as response:
        if response.status == 200:
            logger.info("Document config updated successfully")
            return True
        else:
            error_text = await response.text()
            logger.error(
                f"Failed to update document config: {response.status}, {error_text}"
            )
            return False


async def parse_documents(dataset_id: str, document_ids: list[str]) -> bool:
    """解析文档"""
    session = await get_http_session()

    logger.info(f"Starting parsing for documents: {document_ids}")
    parse_data = {"document_ids": document_ids}
    async with session.post(
        f"/api/v1/datasets/{dataset_id}/chunks", json=parse_data
    ) as response:
        if response.status == 200:
            logger.info("Document parsing started successfully")
            return True
        else:
            error_text = await response.text()
            logger.error(
                f"Failed to start document parsing: {response.status}, {error_text}"
            )
            return False


async def get_document_status(
    dataset_id: str, document_id: str
) -> dict[str, Any] | None:
    """获取文档状态"""
    session = await get_http_session()

    async with session.get(
        f"/api/v1/datasets/{dataset_id}/documents?id={document_id}"
    ) as response:
        if response.status == 200:
            result = await response.json()
            docs = result.get("data", {}).get("docs", [])
            if docs:
                return docs[0]
        return None


async def get_document_chunks_from_api(
    dataset_id: str, document_id: str, is_part_mode: bool = False
) -> list[str]:
    """从API获取文档的分块结果"""
    session = await get_http_session()

    logger.info(
        f"Retrieving chunks for document {document_id}, part_mode: {is_part_mode}"
    )

    all_chunks = []

    if is_part_mode:
        # part模式只需要前10个chunks
        async with session.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            params={"page": 1, "page_size": 10},
        ) as response:
            if response.status == 200:
                result = await response.json()
                data = result.get("data", {})
                chunks = data.get("chunks", [])

                # 提取chunk内容
                chunk_contents = [chunk.get("content", "") for chunk in chunks]
                all_chunks.extend(chunk_contents)

                logger.info(f"Retrieved {len(chunk_contents)} chunks in part mode")
            else:
                error_text = await response.text()
                logger.error(f"Failed to get chunks: {response.status}, {error_text}")
    else:
        # 非part模式需要获取所有chunks
        # 先请求第一页获取total数量
        first_page_size = 100
        async with session.get(
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            params={"page": 1, "page_size": first_page_size},
        ) as response:
            if response.status == 200:
                result = await response.json()
                data = result.get("data", {})
                chunks = data.get("chunks", [])
                total = data.get("total", 0)

                # 提取第一页chunk内容
                chunk_contents = [chunk.get("content", "") for chunk in chunks]
                all_chunks.extend(chunk_contents)

                logger.info(
                    f"Retrieved page 1: {len(chunk_contents)} chunks, total: {total}"
                )

                # 如果还有更多chunks，继续获取剩余的
                if len(all_chunks) < total:
                    remaining_chunks = total - len(all_chunks)
                    # 计算需要获取的页数，使用较大的page_size来减少请求次数
                    remaining_page_size = min(1024, remaining_chunks)
                    page = 2

                    while len(all_chunks) < total:
                        async with session.get(
                            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
                            params={"page": page, "page_size": remaining_page_size},
                        ) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                data = result.get("data", {})
                                chunks = data.get("chunks", [])

                                # 提取chunk内容
                                chunk_contents = [
                                    chunk.get("content", "") for chunk in chunks
                                ]
                                all_chunks.extend(chunk_contents)

                                logger.info(
                                    f"Retrieved page {page}: {len(chunk_contents)} chunks, total so far: {len(all_chunks)}/{total}"
                                )

                                # 如果这页没有更多chunks，退出循环
                                if len(chunks) == 0:
                                    break

                                page += 1
                            else:
                                error_text = await resp.text()
                                logger.error(
                                    f"Failed to get chunks page {page}: {resp.status}, {error_text}"
                                )
                                break
            else:
                error_text = await response.text()
                logger.error(f"Failed to get chunks: {response.status}, {error_text}")

    logger.info(f"Retrieved {len(all_chunks)} chunks successfully")
    return all_chunks


async def wait_for_document_parsing(
    dataset_id: str, document_id: str, max_retries: int = 30, retry_interval: int = 5
) -> bool:
    """等待文档解析完成"""
    logger.info(f"Waiting for document {document_id} parsing to complete...")

    for retry_count in range(max_retries):
        doc_status = await get_document_status(dataset_id, document_id)
        if not doc_status:
            logger.error(f"Could not get document status for {document_id}")
            return False

        run_status = doc_status.get("run", "UNSTART")
        progress_msg = doc_status.get("progress_msg", "")

        if run_status == "DONE":
            logger.info(f"Document {document_id} parsing completed successfully")
            return True
        elif run_status == "FAIL":
            logger.error(f"Document parsing failed: {progress_msg or 'Unknown error'}")
            return False
        elif run_status in ["RUNNING", "UNSTART"]:
            if retry_count % 5 == 0:
                logger.info(
                    f"Document parsing in progress... (retry {retry_count + 1}/{max_retries})"
                )
            await asyncio.sleep(retry_interval)
            continue

    logger.error(
        f"Document parsing timeout after {max_retries * retry_interval} seconds"
    )
    return False


async def upload_and_parse_document(
    file_path: str,
    dataset_name: str = "default",
    chunk_method: str = "naive",
    parser_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    上传文档到RAGFlow并解析分块

    Args:
        file_path: 文件路径或URL
        dataset_name: 数据集名称
        chunk_method: 分块方法
        parser_config: 解析配置

    Returns:
        包含文档信息和分块结果的字典
    """
    logger.info(f"Starting document upload and parsing: {file_path}")
    logger.info(f"Dataset: {dataset_name}, Chunk method: {chunk_method}")

    # 创建或获取数据集
    dataset_id = await create_dataset_if_not_exists(dataset_name)
    if not dataset_id:
        raise Exception(f"Failed to create or get dataset: {dataset_name}")

    # 处理文件路径
    if file_path.startswith(("http://", "https://")):
        # 下载文件
        logger.info(f"Downloading file from URL: {file_path}")
        file_name = file_path.split("/")[-1]
        temp_path = Path(f"/tmp/{file_name}")
        temp_path.parent.mkdir(exist_ok=True)

        success = await download_file_from_url(file_path, temp_path)
        if not success:
            raise Exception(f"Failed to download file from {file_path}")

        file_content = temp_path.read_bytes()
        temp_path.unlink()  # 清理临时文件
        logger.info(f"Downloaded and processed file: {file_name}")
    else:
        # 本地文件
        logger.info(f"Processing local file: {file_path}")
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise Exception(f"File not found: {file_path}")

        file_content = file_path_obj.read_bytes()
        file_name = file_path_obj.name
        logger.info(f"Read local file: {file_name}, size: {len(file_content)} bytes")

    # 上传文档到RAGFlow
    document_id = await upload_document_to_dataset(dataset_id, file_content, file_name)
    if not document_id:
        raise Exception("Failed to upload document")

    # 更新文档解析配置
    config_updated = await update_document_config(
        dataset_id, document_id, chunk_method, parser_config
    )
    if not config_updated:
        logger.warning("Failed to update document config, using default settings")

    # 触发解析
    parse_started = await parse_documents(dataset_id, [document_id])
    if not parse_started:
        raise Exception("Failed to start document parsing")

    # 等待解析完成
    parse_completed = await wait_for_document_parsing(dataset_id, document_id)
    if not parse_completed:
        raise Exception("Document parsing failed or timeout")

    # 获取分块结果
    chunk_texts = await get_document_chunks_from_api(
        dataset_id, document_id, is_part_mode=False
    )

    return {
        "dataset_id": dataset_id,
        "document_id": document_id,
        "document_name": file_name,
        "chunks": chunk_texts,
        "total_chunks": len(chunk_texts),
        "status": "completed",
    }


async def chunk_text_directly(
    text: str, chunk_method: str = "naive", parser_config: dict[str, Any] | None = None
) -> list[str]:
    """
    直接对文本进行分块处理

    Args:
        text: 要分块的文本
        chunk_method: 分块方法
        parser_config: 解析配置

    Returns:
        分块结果列表
    """
    # 创建临时文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as temp_file:
        temp_file.write(text)
        temp_file_path = temp_file.name

    # 使用文档处理功能
    result = await upload_and_parse_document(
        file_path=temp_file_path,
        dataset_name="temp_text_chunking",
        chunk_method=chunk_method,
        parser_config=parser_config,
    )

    # 清理临时文件
    Path(temp_file_path).unlink()

    return result["chunks"]


async def get_document_chunks(
    dataset_id: str, document_id: str, is_part_mode: bool = False
) -> list[str]:
    """
    获取已解析文档的分块结果

    Args:
        dataset_id: 数据集ID
        document_id: 文档ID
        is_part_mode: 是否为part模式，如果是则只返回前10个chunks

    Returns:
        分块结果列表
    """
    return await get_document_chunks_from_api(dataset_id, document_id, is_part_mode)


# 清理函数，在应用关闭时调用
async def cleanup():
    """清理资源"""
    await close_http_session()
