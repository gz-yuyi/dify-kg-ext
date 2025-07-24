import logging
import os
from pathlib import Path
from typing import Any

import requests
from ragflow_sdk import RAGFlow


logger = logging.getLogger(__name__)

# RAGFlow配置
RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "ragflow-test-key-12345")
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")

# 全局RAGFlow客户端
_ragflow_client = None


def get_ragflow_client() -> RAGFlow:
    """获取RAGFlow客户端实例"""
    global _ragflow_client
    if _ragflow_client is None:
        _ragflow_client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
    return _ragflow_client


def download_file_from_url(url: str, target_path: Path) -> bool:
    """从URL下载文件到本地路径"""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    else:
        logger.error(f"Failed to download file from {url}: {response.status_code}")
        return False


def create_dataset_if_not_exists(name: str) -> str:
    """创建数据集（如果不存在）并返回数据集ID"""
    client = get_ragflow_client()

    # 尝试获取已存在的数据集
    existing_datasets = client.list_datasets(name=name)
    if existing_datasets:
        return existing_datasets[0].id

    # 创建新数据集
    dataset = client.create_dataset(name=name)
    return dataset.id


def upload_and_parse_document(
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
    client = get_ragflow_client()

    # 创建或获取数据集
    dataset_id = create_dataset_if_not_exists(dataset_name)
    datasets = client.list_datasets(id=dataset_id)
    if not datasets:
        raise Exception(f"Failed to create or get dataset: {dataset_name}")

    dataset = datasets[0]

    # 处理文件路径
    if file_path.startswith(("http://", "https://")):
        # 下载文件
        file_name = file_path.split("/")[-1]
        temp_path = Path(f"/tmp/{file_name}")
        temp_path.parent.mkdir(exist_ok=True)

        if not download_file_from_url(file_path, temp_path):
            raise Exception(f"Failed to download file from {file_path}")

        file_content = temp_path.read_bytes()
        temp_path.unlink()  # 清理临时文件
    else:
        # 本地文件
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise Exception(f"File not found: {file_path}")

        file_content = file_path_obj.read_bytes()
        file_name = file_path_obj.name

    # 上传文档到RAGFlow
    documents = [{"display_name": file_name, "blob": file_content}]
    dataset.upload_documents(documents)

    # 获取上传的文档
    uploaded_docs = dataset.list_documents(keywords=file_name.split(".")[0])
    if not uploaded_docs:
        raise Exception("Failed to upload document")

    document = uploaded_docs[0]

    # 更新文档解析配置
    update_config = {"chunk_method": chunk_method}
    if parser_config:
        # 构建RAGFlow兼容的parser_config
        ragflow_parser_config = {}
        if "chunk_token_count" in parser_config:
            ragflow_parser_config["chunk_token_num"] = parser_config[
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
                    "chunk_token_num": ragflow_parser_config.get(
                        "chunk_token_num", 128
                    ),
                    "delimiter": ragflow_parser_config.get("delimiter", "\n"),
                    "html4excel": False,
                    "layout_recognize": ragflow_parser_config.get(
                        "layout_recognize", True
                    ),
                    "raptor": {"use_raptor": False},
                }
            )
        elif chunk_method in ["qa", "manual", "paper", "book", "laws", "presentation"]:
            ragflow_parser_config["raptor"] = {"use_raptor": False}
        elif chunk_method in ["table", "picture", "one", "email"]:
            ragflow_parser_config = None

        if ragflow_parser_config:
            update_config["parser_config"] = ragflow_parser_config

    # 更新文档配置
    document.update(update_config)

    # 触发解析
    dataset.async_parse_documents([document.id])

    # 等待解析完成并获取分块结果
    max_retries = 30  # 最多等待30次，每次5秒
    retry_count = 0

    while retry_count < max_retries:
        # 重新获取文档状态
        docs = dataset.list_documents(id=document.id)
        if docs:
            doc = docs[0]
            if doc.run == "DONE":
                # 解析完成，获取分块
                chunks = doc.list_chunks()
                chunk_texts = [chunk.content for chunk in chunks]

                return {
                    "dataset_id": dataset.id,
                    "document_id": document.id,
                    "document_name": file_name,
                    "chunks": chunk_texts,
                    "total_chunks": len(chunk_texts),
                    "status": "completed",
                }
            elif doc.run == "FAIL":
                raise Exception(f"Document parsing failed: {doc.progress_msg}")
            elif doc.run in ["RUNNING", "UNSTART"]:
                # 继续等待
                import time

                time.sleep(5)
                retry_count += 1
                continue
        else:
            raise Exception("Document not found")

    raise Exception("Document parsing timeout")


def chunk_text_directly(
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
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as temp_file:
        temp_file.write(text)
        temp_file_path = temp_file.name

    # 使用文档处理功能
    result = upload_and_parse_document(
        file_path=temp_file_path,
        dataset_name="temp_text_chunking",
        chunk_method=chunk_method,
        parser_config=parser_config,
    )

    # 清理临时文件
    Path(temp_file_path).unlink()

    return result["chunks"]


def get_document_chunks(dataset_id: str, document_id: str) -> list[str]:
    """
    获取已解析文档的分块结果

    Args:
        dataset_id: 数据集ID
        document_id: 文档ID

    Returns:
        分块结果列表
    """
    client = get_ragflow_client()

    datasets = client.list_datasets(id=dataset_id)
    if not datasets:
        raise Exception(f"Dataset not found: {dataset_id}")

    dataset = datasets[0]
    documents = dataset.list_documents(id=document_id)
    if not documents:
        raise Exception(f"Document not found: {document_id}")

    document = documents[0]
    chunks = document.list_chunks()

    return [chunk.content for chunk in chunks]
