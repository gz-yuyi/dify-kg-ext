from typing import Any, ClassVar

from pydantic import BaseModel, Field, RootModel, field_validator


class RetrievalMetadataCondition(BaseModel):
    name: list[str] = Field(..., description="要过滤的元数据名称列表")
    comparison_operator: str = Field(..., description="比较运算符")
    value: str | None = Field(None, description="比较值")


class MetadataConditions(BaseModel):
    logical_operator: str = Field("and", description="逻辑运算符：and或or")
    conditions: list[RetrievalMetadataCondition] = Field(..., description="条件列表")


class RetrievalSetting(BaseModel):
    top_k: int = Field(..., gt=0, le=100, description="返回结果的最大数量")
    score_threshold: float = Field(
        ..., ge=0, le=1, description="结果与查询的相关性分数阈值"
    )


class RetrievalRequest(BaseModel):
    knowledge_id: str = Field(..., description="知识库唯一ID")
    query: str = Field(..., min_length=1, description="用户查询")
    retrieval_setting: RetrievalSetting = Field(..., description="检索参数")
    metadata_condition: MetadataConditions | None = Field(
        None, description="元数据过滤条件"
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v):
        if not v.strip():
            raise ValueError("查询不能为空")
        return v

    @field_validator("knowledge_id")
    @classmethod
    def validate_knowledge_id(cls, v):
        return v.replace("_", "-")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "knowledge_id": "your-knowledge-id",
                "query": "社保问题",
                "retrieval_setting": {"top_k": 2, "score_threshold": 0.5},
            }
        }


class RecordMetadata(RootModel):
    """文档元数据"""

    root: dict[str, Any] = Field(default_factory=dict)


class Record(BaseModel):
    content: str = Field(..., description="知识库中数据源的文本块")
    score: float = Field(..., ge=0, description="结果与查询的相关性分数")
    title: str = Field(..., description="文档标题")
    metadata: dict[str, Any] | None = Field(None, description="文档元数据")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "metadata": {
                    "path": "s3://dify/knowledge.txt",
                    "description": "dify knowledge document",
                },
                "score": 0.98,
                "title": "knowledge.txt",
                "content": "This is the document for external knowledge.",
            }
        }


class RetrievalResponse(BaseModel):
    records: list[Record] = Field(..., description="知识库查询记录列表")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "records": [
                    {
                        "metadata": {
                            "path": "s3://dify/knowledge.txt",
                            "description": "dify knowledge document",
                        },
                        "score": 0.98,
                        "title": "knowledge.txt",
                        "content": "This is the document for external knowledge.",
                    }
                ]
            }
        }


class ErrorResponse(BaseModel):
    error_code: int = Field(..., description="错误代码")
    error_msg: str = Field(..., description="API异常描述")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "error_code": 1001,
                "error_msg": "Invalid Authorization header format. Expected 'Bearer <api-key>' format.",
            }
        }
