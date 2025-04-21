import os
from typing import List

import aiohttp
from pydantic import BaseModel, ConfigDict

from . import RerankResult

__all__ = ["embedding", "rerank"]

BASE_URL = "https://api.siliconflow.cn/v1"

TOKEN = os.getenv("SILICONFLOW_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


class RerankResponse(BaseModel):

    class Meta(BaseModel):
        class BilledUnits(BaseModel):
            input_tokens: int
            output_tokens: int
            search_units: int
            classifications: int

            model_config = ConfigDict(
                json_schema_extra={
                    "example": {
                        "input_tokens": 27,
                        "output_tokens": 0,
                        "search_units": 0,
                        "classifications": 0,
                    }
                }
            )

        class Tokens(BaseModel):
            input_tokens: int
            output_tokens: int

            model_config = ConfigDict(
                json_schema_extra={"example": {"input_tokens": 27, "output_tokens": 0}}
            )

        billed_units: "RerankResponse.Meta.BilledUnits"
        tokens: "RerankResponse.Meta.Tokens"

        model_config = ConfigDict(
            json_schema_extra={
                "example": {
                    "billed_units": {
                        "input_tokens": 27,
                        "output_tokens": 0,
                        "search_units": 0,
                        "classifications": 0,
                    },
                    "tokens": {"input_tokens": 27, "output_tokens": 0},
                }
            }
        )

    id: str
    results: List[RerankResult]
    meta: Meta

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "019380a54d8e76f19565ea2377e414ee",
                "results": [
                    {
                        "document": {"text": "doc3"},
                        "index": 2,
                        "relevance_score": 0.00019110432,
                    },
                    {
                        "document": {"text": "doc1"},
                        "index": 0,
                        "relevance_score": 0.00017952797,
                    },
                ],
                "meta": {
                    "billed_units": {
                        "input_tokens": 27,
                        "output_tokens": 0,
                        "search_units": 0,
                        "classifications": 0,
                    },
                    "tokens": {"input_tokens": 27, "output_tokens": 0},
                },
            }
        }
    )


async def rerank(documents: List[str], query: str) -> List[RerankResult]:
    url = f"{BASE_URL}/rerank"
    payload = {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": query,
        "documents": documents,
        "top_n": len(documents),
        "return_documents": True,
        "max_chunks_per_doc": 123,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=HEADERS) as response:
            response_dict = await response.json()
            response = RerankResponse.model_validate(response_dict)
            return response.results


class EmbeddingResponse(BaseModel):
    class EmbeddingData(BaseModel):
        object: str
        embedding: List[float]
        index: int

        model_config = ConfigDict(
            json_schema_extra={
                "example": {"object": "embedding", "embedding": [123.0], "index": 123}
            }
        )

    class Usage(BaseModel):
        prompt_tokens: int
        completion_tokens: int
        total_tokens: int

        model_config = ConfigDict(
            json_schema_extra={
                "example": {
                    "prompt_tokens": 123,
                    "completion_tokens": 123,
                    "total_tokens": 123,
                }
            }
        )

    model: str
    data: List[EmbeddingData]
    usage: Usage

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "text-embedding-ada-002",
                "data": [{"object": "embedding", "embedding": [123.0], "index": 123}],
                "usage": {
                    "prompt_tokens": 123,
                    "completion_tokens": 123,
                    "total_tokens": 123,
                },
            }
        }
    )


async def embedding(input_text: str) -> List[float]:
    url = f"{BASE_URL}/embeddings"
    payload = {
        "model": "BAAI/bge-m3",
        "input": input_text,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=HEADERS) as response:
            response_dict = await response.json()
            return response_dict["data"][0]["embedding"]
