from fastapi import FastAPI, HTTPException, Header, Depends

from dify_kg_ext.dataclasses import (
    Knowledge, 
    KnowledgeDeleteRequest,
    KnowledgeBindBatchRequest, 
    KnowledgeUnbindBatchRequest,
    BaseResponse,
    BindBatchResponse,
    UnbindBatchResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    RetrievalRequest,
    RetrievalResponse,
    ErrorResponse
)
from dify_kg_ext.es import (
    index_document, 
    delete_documents, 
    bind_knowledge_to_library, 
    unbind_knowledge_from_library,
    search_knowledge,
    retrieve_knowledge,
    check_knowledge_exists
)

app = FastAPI()

@app.post("/knowledge/update", response_model=BaseResponse)
async def update_knowledge(knowledge: Knowledge):
    """
    添加或更新知识条目
    """
    segment_id = await index_document(knowledge)
    if not segment_id:
        raise HTTPException(status_code=500, detail="Failed to index document")
        
    return {
        "code": 200,
        "msg": "success"
    }

@app.post("/knowledge/delete", response_model=BaseResponse)
async def delete_knowledge(request: KnowledgeDeleteRequest):
    """
    删除指定的知识条目
    """
    await delete_documents(request.segment_ids)
    return {
        "code": 200,
        "msg": "success"
    }

@app.post("/knowledge/bind_batch", response_model=BindBatchResponse)
async def bind_knowledge_batch(request: KnowledgeBindBatchRequest):
    """
    批量绑定知识条目到指定库
    """
    result = await bind_knowledge_to_library(
        library_id=request.library_id,
        category_ids=request.category_ids
    )
    
    return {
        "code": 200,
        "msg": "success",
        "data": result
    }

@app.post("/knowledge/unbind_batch", response_model=UnbindBatchResponse)
async def unbind_knowledge_batch(request: KnowledgeUnbindBatchRequest):
    """
    解除知识条目与指定库的绑定
    """
    result = await unbind_knowledge_from_library(
        library_id=request.library_id,
        category_ids=request.category_ids,
        delete_type=request.delete_type
    )
    
    return {
        "code": 200,
        "msg": "success",
        "data": result
    }

@app.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(request: KnowledgeSearchRequest):
    """
    搜索知识条目
    """
    result = await search_knowledge(
        query=request.query,
        library_id=request.library_id,
        limit=request.limit
    )
    
    # Convert Pydantic objects to dictionaries for serialization
    segments_dict = [segment.model_dump() for segment in result["segments"]]
    
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "segments": segments_dict
        }
    }

# 验证API密钥的函数
async def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": 1001,
                "error_msg": "Missing Authorization header"
            }
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": 1001,
                "error_msg": "Invalid Authorization header format. Expected 'Bearer <api-key>' format."
            }
        )
    
    # 实际项目中，应该从配置或数据库中验证API密钥
    api_key = parts[1]
    if api_key != "your-api-key":  # 这里应替换为实际的验证逻辑
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": 1002,
                "error_msg": "Authorization failed"
            }
        )
    
    return api_key

@app.post("/retrieval", response_model=RetrievalResponse, responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def retrieval(request: RetrievalRequest, api_key: str = Depends(verify_api_key)):
    """
    从外部知识库检索数据
    """
    try:
        # 检查知识库是否存在
        if not await check_knowledge_exists(request.knowledge_id):
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": 2001,
                    "error_msg": "The knowledge does not exist"
                }
            )
        
        result = await retrieve_knowledge(
            knowledge_id=request.knowledge_id,
            query=request.query,
            top_k=request.retrieval_setting.top_k,
            score_threshold=request.retrieval_setting.score_threshold,
            metadata_condition=request.metadata_condition
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": 5001,
                "error_msg": f"Internal server error: {str(e)}"
            }
        ) 