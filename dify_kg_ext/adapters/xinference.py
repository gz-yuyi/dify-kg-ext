import os
from typing import List

import aiohttp

from . import RerankResult

__all__ = ["embedding", "rerank"]


BASE_URL = os.getenv("XINFERENCE_HOST")

auth_headers = {
    "Authorization": f"Bearer xxx",
    "Content-Type": "application/json",
}


async def embedding(input_text: str) -> List[float]:
    url = f"{BASE_URL}/v1/embeddings"
    request_body = {
        "model": "bge-m3",
        "input": input_text,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=request_body, headers=auth_headers
        ) as response:
            response_data = await response.json()
            return response_data["data"][0]["embedding"]


async def rerank(
    documents: List[str],
    query: str,
) -> List[RerankResult]:
    url = f"{BASE_URL}/v1/rerank"
    request_body = {
        "model": "bge-reranker-v2-m3",
        "documents": documents,
        "query": query,
        "top_n": len(documents),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=request_body, headers=auth_headers
        ) as response:
            response_data = await response.json()
            return [
                RerankResult.model_validate(item) for item in response_data["results"]
            ]
