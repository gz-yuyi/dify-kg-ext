from fastapi import FastAPI, HTTPException

from dify_kg_ext.dataclasses import (
    Knowledge, 
    KnowledgeDeleteRequest,
    KnowledgeBindBatchRequest, 
    KnowledgeUnbindBatchRequest,
    BaseResponse,
    BindBatchResponse,
    UnbindBatchResponse
)
from dify_kg_ext.es import (
    index_document, 
    delete_documents, 
    bind_knowledge_to_library, 
    unbind_knowledge_from_library
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