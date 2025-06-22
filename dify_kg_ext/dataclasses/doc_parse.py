from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# === New models for document chunking API ===
class UploadDocumentRequest(BaseModel):
    """Request model for uploading a document"""

    file_path: str = Field(
        ...,
        description="URL or path to the document to be processed",
        example="http://39.105.167.2:9529/template.pdf",
    )

    class Config:
        json_schema_extra = {
            "example": {"file_path": "http://39.105.167.2:9529/template.pdf"}
        }


class UploadDocumentResponse(BaseModel):
    """Response model after document upload"""

    dataset_id: str = Field(
        ...,
        description="Unique identifier for the dataset",
        example="f6c5dc32298211f08b470242ac130006",
    )
    document_id: str = Field(
        ...,
        description="Unique identifier for the full document",
        example="f86a8ad8298211f0985d0242ac130006",
    )
    document_name: str = Field(
        ..., description="Name of the uploaded document", example="template.pdf"
    )
    part_document_id: str = Field(
        ...,
        description="Identifier for the partial document (for faster processing)",
        example="fb783ab8298211f0afbf0242ac130006",
    )
    part_document_name: str = Field(
        ..., description="Name of the partial document", example="part_template.pdf"
    )
    sign: bool = Field(
        default=True, description="Success indicator for the operation", example=True
    )

    class Config:
        json_schema_extra = {
            "example": {
                "dataset_id": "f6c5dc32298211f08b470242ac130006",
                "document_id": "f86a8ad8298211f0985d0242ac130006",
                "document_name": "template.pdf",
                "part_document_id": "fb783ab8298211f0afbf0242ac130006",
                "part_document_name": "part_template.pdf",
                "sign": True,
            }
        }


class ParserConfig(BaseModel):
    """Configuration for document parsing"""

    chunk_token_count: Optional[int] = Field(
        default=128, description="Token count per chunk", example=128
    )
    layout_recognize: Optional[bool] = Field(
        default=True, description="Enable layout recognition", example=True
    )
    html4excel: Optional[bool] = Field(
        default=False,
        description="Convert Excel documents to HTML format",
        example=False,
    )
    delimiter: Optional[str] = Field(
        default="\n", description="Text delimiter for chunking", example="\n"
    )
    task_page_size: Optional[int] = Field(
        default=12, description="Page size for PDF processing", example=12
    )
    raptor: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"use_raptor": False},
        description="RAPTOR configuration settings",
        example={"use_raptor": False},
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_token_count": 128,
                "layout_recognize": True,
                "html4excel": False,
                "delimiter": "\n",
                "task_page_size": 12,
                "raptor": {"use_raptor": False},
            }
        }


class AnalyzingDocumentRequest(BaseModel):
    """Request model for document parsing"""

    dataset_id: str = Field(
        ...,
        description="Dataset ID for the document",
        example="f6c5dc32298211f08b470242ac130006",
    )
    document_id: str = Field(
        ...,
        description="Document ID to be processed",
        example="fb783ab8298211f0afbf0242ac130006",
    )
    document_name: str = Field(
        ...,
        description="Name of the document to be processed",
        example="part-template.pdf",
    )
    chunk_method: Literal[
        "naive",
        "manual",
        "qa",
        "table",
        "paper",
        "book",
        "laws",
        "presentation",
        "picture",
        "email",
    ] = Field(..., description="Document parsing method to use", example="laws")
    parser_flag: int = Field(
        ...,
        description="Flag indicating if parser config should be used (1=true, 0=false)",
        example=0,
    )
    parser_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration settings for the parser",
        example={"chunk_token_count": 10, "layout_recognize": True, "delimiter": "\n"},
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "dataset_id": "f6c5dc32298211f08b470242ac130006",
                    "document_id": "fb783ab8298211f0afbf0242ac130006",
                    "document_name": "part-template.pdf",
                    "chunk_method": "laws",
                    "parser_flag": 0,
                    "parser_config": {},
                },
                {
                    "dataset_id": "f6c5dc32298211f08b470242ac130006",
                    "document_id": "fb783ab8298211f0afbf0242ac130006",
                    "document_name": "part-template.pdf",
                    "chunk_method": "naive",
                    "parser_flag": 1,
                    "parser_config": {
                        "chunk_token_count": 10,
                        "layout_recognize": True,
                        "delimiter": "\n",
                    },
                },
            ]
        }


class AnalyzingDocumentResponse(BaseModel):
    """Response model with document chunks"""

    chunks: List[str] = Field(
        ...,
        description="List of text chunks extracted from the document",
        example=[
            "中华人民共和国网络安全法\n（2016 年11 月7日第十二届全国人民代表大会常务委员会第二十四次会议通过）目录",
            "第三章网络运行安全\n第一节一般规定",
        ],
    )
    sign: bool = Field(
        default=True, description="Success indicator for the operation", example=True
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chunks": [
                    "中华人民共和国网络安全法\n（2016 年11 月7日第十二届全国人民代表大会常务委员会第二十四次会议通过）目录",
                    "第三章网络运行安全\n第一节一般规定",
                    "第一章总则\n第一条为了保障网络安全，维护网络空间主权和国家安全、社会公共利益，保护公民、法人和其他组织的合法权益，促进经济社会信息化健康发展，制定本法。",
                ],
                "sign": True,
            }
        }