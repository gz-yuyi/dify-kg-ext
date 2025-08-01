# Dify External Knowledge API 实现文档

## 概述

本项目实现了与Dify平台完全兼容的External Knowledge API接口，允许Dify平台从外部知识库检索信息。该实现遵循Dify官方API规范，确保无缝集成。

## 功能特性

- ✅ 完全兼容Dify External Knowledge API规范
- ✅ 支持Bearer Token认证
- ✅ 语义搜索和向量检索
- ✅ 可配置的相关性分数阈值
- ✅ 可配置的返回结果数量(top_k)
- ✅ 元数据过滤支持
- ✅ 标准化错误响应格式
- ✅ 健康检查接口
- ✅ 完整的API文档(OpenAPI/Swagger)

## 架构设计

```
Dify平台 -----> Knowledge Database API -----> 本地知识库(Elasticsearch)
              (端口5001, /retrieval端点)        (向量搜索+语义检索)
```

## 快速开始

### 1. 启动Knowledge Database API服务

```bash
python main.py serve --host 0.0.0.0 --port 5001
```

启动成功后，你会看到：
```
Starting Knowledge Database API server on 0.0.0.0:5001
Features:
  ✅ Knowledge Management API
  ✅ Dify External Knowledge API
  ✅ Semantic Search & Vector Retrieval

📖 API Documentation: http://0.0.0.0:5001/docs
🏥 Health Check: http://0.0.0.0:5001/health
🤖 Dify Retrieval Endpoint: http://0.0.0.0:5001/retrieval
```

### 2. 在Dify中配置外部知识库

在Dify平台中，按以下步骤配置外部知识库：

1. 进入知识库设置
2. 选择"外部知识库"
3. 配置API端点：`http://your-server:5001/retrieval`
4. 设置API密钥：使用任意长度超过10位的字符串作为Bearer Token
5. 测试连接

## API接口文档

### 主要端点

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/retrieval` | 知识检索接口（Dify调用） |
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |
| GET | `/docs` | API文档 |

### 知识检索接口

#### 请求格式

```http
POST /retrieval HTTP/1.1
Content-Type: application/json
Authorization: Bearer your-api-key

{
    "knowledge_id": "your-knowledge-id",
    "query": "用户查询文本",
    "retrieval_setting": {
        "top_k": 5,
        "score_threshold": 0.5
    },
    "metadata_condition": {
        "logical_operator": "and",
        "conditions": [
            {
                "name": ["category"],
                "comparison_operator": "eq",
                "value": "技术文档"
            }
        ]
    }
}
```

#### 参数说明

- `knowledge_id`: 知识库唯一标识符（对应本系统的library_id）
- `query`: 用户查询文本
- `retrieval_setting`: 检索配置
  - `top_k`: 返回结果的最大数量（1-100）
  - `score_threshold`: 相关性分数阈值（0.0-1.0）
- `metadata_condition`: 可选的元数据过滤条件

#### 响应格式

成功响应（200）：
```json
{
    "records": [
        {
            "content": "这是检索到的知识内容...",
            "score": 0.85,
            "title": "文档标题",
            "metadata": {
                "document_id": "doc_123",
                "category_id": "cat_456",
                "knowledge_type": "faq",
                "keywords": ["关键词1", "关键词2"]
            }
        }
    ]
}
```

错误响应示例：
```json
{
    "error_code": 1001,
    "error_msg": "Invalid Authorization header format. Expected 'Bearer <api-key>' format."
}
```

### 错误代码说明

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| 1001 | 403 | 认证头格式错误 |
| 1002 | 403 | 认证失败 |
| 2001 | 404 | 知识库不存在 |
| 5001 | 500 | 内部服务器错误 |

## 测试示例

### 使用curl测试

```bash
# 健康检查
curl -X GET "http://localhost:5001/health"

# 知识检索测试
curl -X POST "http://localhost:5001/retrieval" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-api-key-123456" \
  -d '{
    "knowledge_id": "lib_123456",
    "query": "社保问题咨询",
    "retrieval_setting": {
      "top_k": 3,
      "score_threshold": 0.5
    }
  }'
```

### 使用Python测试

```python
import requests

# 测试请求
url = "http://localhost:5001/retrieval"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer test-api-key-123456"
}

data = {
    "knowledge_id": "lib_123456",
    "query": "如何查询社保缴费记录？",
    "retrieval_setting": {
        "top_k": 5,
        "score_threshold": 0.3
    }
}

response = requests.post(url, json=data, headers=headers)
print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")
```

## 与现有API的关系

本项目提供统一的API服务，包含以下功能：

**统一API服务** (端口5001) - 包含所有功能：

1. **知识管理API** - 用于知识库的CRUD操作
   - 添加/更新知识：`POST /knowledge/update`
   - 删除知识：`POST /knowledge/delete`
   - 绑定知识库：`POST /knowledge/bind_batch`
   - 搜索知识：`POST /knowledge/search`

2. **Dify External Knowledge API** - 为Dify平台提供
   - 知识检索：`POST /retrieval`

3. **系统功能**
   - 健康检查：`GET /health`
   - 服务信息：`GET /`
   - API文档：`GET /docs`

启动单个服务即可获得所有功能：

```bash
# 启动统一API服务
python main.py serve --port 5001
```

## 配置说明

### API密钥验证

当前实现使用简单的API密钥验证：
- API密钥长度必须大于10位
- 生产环境应该实现更严格的验证逻辑

要自定义API密钥验证，请修改 `dify_kg_ext/entrypoints/dify_external_api.py` 中的 `verify_dify_api_key` 函数。

### 知识库映射

- Dify中的 `knowledge_id` 对应本系统的 `library_id`
- 确保在使用前已通过知识管理API绑定了相关知识点到指定的library_id

### 部署建议

1. **生产环境部署**：
   - 使用环境变量管理配置
   - 实现更安全的API密钥验证
   - 配置日志记录
   - 使用反向代理(如Nginx)

2. **监控和调试**：
   - 查看服务日志获取详细请求信息
   - 使用 `/health` 端点进行健康检查
   - 访问 `/docs` 查看完整API文档

3. **性能优化**：
   - 配置Elasticsearch连接池
   - 调整检索参数以平衡准确性和性能
   - 考虑添加缓存机制

## 故障排除

### 常见问题

1. **连接失败**：
   - 检查服务是否正常启动
   - 确认端口是否被占用
   - 检查防火墙设置

2. **认证失败**：
   - 确认API密钥格式正确（Bearer token）
   - 检查API密钥长度（需大于10位）

3. **知识库不存在**：
   - 确认knowledge_id在系统中存在
   - 检查是否已绑定相关知识点

4. **检索结果为空**：
   - 检查分数阈值设置是否过高
   - 确认知识库中有相关内容
   - 调整top_k参数

### 日志查看

服务启动后会输出详细日志，包括：
- 请求信息：knowledge_id, query, top_k等
- 响应信息：返回记录数量
- 错误信息：详细的错误堆栈

## 版本更新

当前版本：v1.0.0

主要特性：
- 实现Dify External Knowledge API规范
- 支持语义搜索和向量检索
- 提供完整的错误处理和文档

未来计划：
- 支持更多元数据过滤条件
- 优化检索性能
- 添加API使用统计
- 支持多租户
