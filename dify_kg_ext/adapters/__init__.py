import os

from pydantic import BaseModel, ConfigDict


class RerankResult(BaseModel):
    class Document(BaseModel):
        text: str

        model_config = ConfigDict(json_schema_extra={"example": {"text": "doc3"}})

    document: Document | None
    index: int
    relevance_score: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document": {"text": "doc3"},
                "index": 2,
                "relevance_score": 0.00019110432,
            }
        }
    )


if os.getenv("SMALL_MODEL_BACKEND") == "xinference":
    from .xinference import embedding as embedding
    from .xinference import rerank as rerank
elif os.getenv("SMALL_MODEL_BACKEND") == "siliconflow":
    from .siliconflow import embedding as embedding
    from .siliconflow import rerank as rerank
else:
    from .xinference import embedding as embedding
    from .xinference import rerank as rerank
