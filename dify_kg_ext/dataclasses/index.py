from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, RootModel, field_validator


class Answer(BaseModel):
    content: str = Field(..., min_length=1, description="答案内容")
    channels: list[str] = Field(..., min_items=1, description="渠道ID列表")

    @field_validator("channels")
    @classmethod
    def validate_channels_not_empty(cls, v):
        if not v:
            raise ValueError("至少需要提供一个渠道ID")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "content": "您好，社保征缴问题可拨打0769-12366咨询，或向智能客服提问。",
                "channels": ["channel_a", "channel_b"],
            }
        }


class Knowledge(BaseModel):
    segment_id: str = Field(..., min_length=1, description="知识点ID")
    source: Literal["personal", "system"] = Field(
        ..., description="来源类型：个人知识库或系统知识库"
    )
    knowledge_type: Literal["segment", "faq"] = Field(
        ..., description="知识类型：片段或FAQ"
    )
    question: str | None = Field(None, description="问题文本（FAQ类型必填）")
    similar_questions: list[str] | None = Field(None, description="相似问题列表")
    answers: list[Answer] = Field(..., min_items=1, description="答案列表（含渠道）")
    weight: int = Field(..., ge=0, description="知识点权重")
    document_id: str | None = Field(None, description="关联文档ID")
    keywords: list[str] | None = Field(None, description="关键字列表")
    category_id: str | None = Field(None, description="知识类别ID")

    @field_validator("question")
    @classmethod
    def validate_question_for_faq(cls, v, info):
        if info.data.get("knowledge_type") == "faq" and not v:
            raise ValueError("FAQ知识类型必须提供问题")
        return v

    @field_validator("answers")
    @classmethod
    def validate_answers_not_empty(cls, v):
        if not v:
            raise ValueError("至少需要提供一个答案")
        return v

    @field_validator("similar_questions")
    @classmethod
    def validate_similar_questions(cls, v, info):
        if v and any(not q.strip() for q in v):
            raise ValueError("相似问题不能包含空字符串")
        return v

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        if v and any(not k.strip() for k in v):
            raise ValueError("关键字不能包含空字符串")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "segment_id": "id_xxx",
                "source": "personal",
                "knowledge_type": "faq",
                "question": "社保征缴相关问题指引口径？",
                "similar_questions": [
                    "如何了解社保征缴相关问题？",
                    "社保缴费问题如何咨询？",
                ],
                "answers": [
                    {
                        "content": "您好，在办理社保缴费登记、申报社保缴费业务时如有疑问，可拨打0769-12366纳税缴费服务热线咨询。",
                        "channels": ["channel_a", "channel_b"],
                    }
                ],
                "weight": 5,
                "document_id": "doc_789",
                "keywords": ["社保", "征缴", "咨询"],
                "category_id": "cat_001",
            }
        }


class KnowledgeDeleteRequest(BaseModel):
    segment_ids: list[str] = Field(..., min_items=1, description="要删除的知识点ID列表")

    @field_validator("segment_ids")
    @classmethod
    def validate_segment_ids_not_empty(cls, v):
        if not v:
            raise ValueError("至少需要提供一个知识点ID")
        if any(not id.strip() for id in v):
            raise ValueError("知识点ID不能为空")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"segment_ids": ["id_xxx", "id_yyy"]}
        }


class KnowledgeBindBatchRequest(BaseModel):
    library_id: str = Field(..., min_length=1, description="库ID")
    category_ids: list[str] = Field(..., min_items=1, description="绑定类别ID列表")

    @field_validator("library_id")
    @classmethod
    def validate_library_id(cls, v):
        if not v.strip():
            raise ValueError("库ID不能为空")
        return v

    @field_validator("category_ids")
    @classmethod
    def validate_category_ids_not_empty(cls, v):
        if not v:
            raise ValueError("至少需要提供一个类别ID")
        if any(not id.strip() for id in v):
            raise ValueError("类别ID不能为空")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "library_id": "lib_123456",
                "category_ids": ["cat_001", "cat_002", "cat_003"],
            }
        }


class KnowledgeUnbindBatchRequest(BaseModel):
    library_id: str = Field(..., min_length=1, description="库ID")
    category_ids: list[str] = Field(..., description="要解绑的类别ID列表")
    delete_type: Literal["all", "part"] = Field(..., description="解绑类型：全部或部分")

    @field_validator("library_id")
    @classmethod
    def validate_library_id(cls, v):
        if not v.strip():
            raise ValueError("库ID不能为空")
        return v

    @field_validator("category_ids")
    @classmethod
    def validate_category_ids(cls, v, info):
        if info.data.get("delete_type") == "part" and not v:
            raise ValueError("当解绑类型为'部分'时，类别ID列表不能为空")
        if v and any(not id.strip() for id in v):
            raise ValueError("类别ID不能为空")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "library_id": "lib_123456",
                "category_ids": ["cat_001", "cat_002"],
                "delete_type": "part",
            }
        }


class BindBatchResponseData(BaseModel):
    success_count: int = Field(..., ge=0, description="成功绑定的数量")
    failed_ids: list[str] = Field(default_factory=list, description="绑定失败的ID列表")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"success_count": 3, "failed_ids": []}
        }


class UnbindBatchResponseData(BaseModel):
    success_count: int = Field(..., ge=0, description="成功解绑的数量")
    failed_ids: list[str] = Field(default_factory=list, description="解绑失败的ID列表")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"success_count": 2, "failed_ids": []}
        }


class BaseResponse(BaseModel):
    code: int = Field(..., description="响应代码")
    msg: str = Field(..., description="响应消息")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"code": 200, "msg": "success"}
        }


class BindBatchResponse(BaseResponse):
    data: BindBatchResponseData

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "code": 200,
                "msg": "success",
                "data": {"success_count": 3, "failed_ids": []},
            }
        }


class UnbindBatchResponse(BaseResponse):
    data: UnbindBatchResponseData

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "code": 200,
                "msg": "success",
                "data": {"success_count": 2, "failed_ids": []},
            }
        }


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词")
    library_id: str = Field(..., min_length=1, description="要搜索的知识库ID")
    limit: int = Field(10, gt=0, le=100, description="返回结果数量限制")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v):
        if not v.strip():
            raise ValueError("搜索关键词不能为空")
        return v

    @field_validator("library_id")
    @classmethod
    def validate_library_id(cls, v):
        if not v.strip():
            raise ValueError("知识库ID不能为空")
        return v

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {"query": "社保问题", "library_id": "lib_123456", "limit": 10}
        }


class KnowledgeSearchResponseData(BaseModel):
    segments: list[Knowledge] = Field(..., description="搜索到的知识列表")

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "segments": [
                    {
                        "segment_id": "id_xxx",
                        "source": "personal",
                        "knowledge_type": "faq",
                        "question": "社保征缴相关问题指引口径？",
                        "similar_questions": [
                            "如何了解社保征缴相关问题？",
                            "社保缴费问题如何咨询？",
                        ],
                        "answers": [
                            {
                                "content": "您好，在办理社保缴费登记、申报社保缴费业务时如有疑问，可拨打0769-12366纳税缴费服务热线咨询。",
                                "channels": ["channel_a", "channel_b"],
                            }
                        ],
                        "weight": 5,
                        "document_id": "doc_789",
                        "keywords": ["社保", "征缴", "咨询"],
                        "category_id": "cat_001",
                    }
                ]
            }
        }


class KnowledgeSearchResponse(BaseResponse):
    data: KnowledgeSearchResponseData

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "code": 200,
                "msg": "success",
                "data": {
                    "segments": [
                        {
                            "segment_id": "id_xxx",
                            "source": "personal",
                            "knowledge_type": "faq",
                            "question": "社保征缴相关问题指引口径？",
                            "similar_questions": [
                                "如何了解社保征缴相关问题？",
                                "社保缴费问题如何咨询？",
                            ],
                            "answers": [
                                {
                                    "content": "您好，在办理社保缴费登记、申报社保缴费业务时如有疑问，可拨打0769-12366纳税缴费服务热线咨询。",
                                    "channels": ["channel_a", "channel_b"],
                                }
                            ],
                            "weight": 5,
                            "document_id": "doc_789",
                            "keywords": ["社保", "征缴", "咨询"],
                            "category_id": "cat_001",
                        }
                    ]
                },
            }
        }


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
    score: float = Field(..., ge=0, le=1, description="结果与查询的相关性分数")
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

    # validate title as string
    @field_validator("title")
    @classmethod
    def validate_channels_not_empty(cls, v):
        if not isinstance(v, str):
            return ""
        return v


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
