"""
西安补丁
"""

import os

import aiohttp

from . import RerankResult


__all__ = ["embedding", "rerank"]


# vLLM URLs
VLLM_EMBEDDING_URL = os.getenv("VLLM_URL", "http://vllm-embedding:8000")
VLLM_RERANK_URL = os.getenv("VLLM_RERANK_URL", "http://vllm-rerank:8000")
API_KEY = os.getenv("VLLM_API_KEY")

HEADERS = {"Content-Type": "application/json"}
if API_KEY:
    HEADERS["Authorization"] = f"Bearer {API_KEY}"


async def embedding(input_text: str) -> list[float]:
    """
    调用 vLLM 的 embedding 接口获取文本向量

    Args:
        input_text: 输入文本，可以是单个字符串或字符串列表

    Returns:
        向量列表，如果输入是列表则返回向量列表的列表
    """
    url = f"{VLLM_EMBEDDING_URL}/v1/embeddings"
    payload = {
        "input": input_text if isinstance(input_text, list) else [input_text],
        "model": "bge-m3",  # 默认模型，可以通过环境变量配置
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(url, json=payload, headers=HEADERS) as response,
    ):
        response_data = await response.json()

        return response_data["data"][0]["embedding"]


async def rerank(documents: list[str], query: str) -> list[RerankResult]:
    """
    调用 vLLM 的 rerank 接口对文档进行重新排序

    Args:
        documents: 文档列表
        query: 查询文本

    Returns:
        重新排序的结果列表
    """
    url = f"{VLLM_RERANK_URL}/v2/rerank"
    payload = {
        "model": "BAAI/bge-reranker-m3-v2",  # 默认模型，可以通过环境变量配置
        "query": query,
        "documents": documents,
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(url, json=payload, headers=HEADERS) as response,
    ):
        response_data = await response.json()

        results = response_data["results"]

        # 转换为标准的 RerankResult 格式
        rerank_results = []
        for result in results:
            rerank_result = RerankResult(
                document=RerankResult.Document(text=result["document"]["text"]),
                index=result["index"],
                relevance_score=result["document"]["relevance_score"],
            )
            rerank_results.append(rerank_result)

        return rerank_results
