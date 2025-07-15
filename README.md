# knowledge-database

语义科技智能体平台知识库

## 功能特性

- 🔍 语义搜索和向量检索
- 📚 知识库管理（增删改查）
- 🔗 知识点绑定和解绑
- 📄 **文档处理** - 自动解析和分块文档
- ✂️ **文本分块** - 直接文本处理和智能分块
- 🤖 **Dify平台集成** - 提供Dify兼容的外部知识库API
- 📊 基于Elasticsearch的高性能搜索
- 🚀 FastAPI异步框架

## 环境要求
- Linux
- uv
- Docker & Docker Compose（推荐）
- Elasticsearch（Docker自动提供）
- Redis（Docker自动提供）
- Python 3.12+（本地开发）
- SiliconFlow API Token（用于文档解析）

## 安装和运行

### 安装依赖
```shell
uv sync
```

### Docker方式（推荐）

#### 使用Docker Compose（一键启动完整环境）
```shell
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件（可选，使用默认配置可直接跳过）
nano .env

# 构建并启动所有服务（API + Worker + Redis + Elasticsearch）
docker-compose up --build

# 后台运行
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 单独使用Docker
```shell
# 构建镜像
docker build -t knowledge-db .

# 运行API服务
docker run -p 5001:5001 knowledge-db

# 运行Worker
docker run knowledge-db python -m main.py worker
```

### 本地开发方式

#### 启动API服务（包含Dify集成）
```shell
python main.py serve --host 0.0.0.0 --port 5001
```

一个服务提供所有功能：
- 知识管理API (CRUD操作)
- Dify外部知识库API (`/retrieval`端点)
- 健康检查和API文档

#### 启动文档处理Worker
文档解析需要Celery worker异步处理。启动worker：
```shell
python main.py worker
```

自定义worker选项：
```shell
# 使用8个进程
python main.py worker --concurrency 8

# 调试日志级别
python main.py worker --loglevel debug

# 监听特定队列
python main.py worker --queues document_parse
```

## 可用命令

```bash
# 查看所有可用命令
python main.py --help

# 启动API服务（包含知识管理+Dify集成，默认端口5001）
python main.py serve

# 开发模式（自动重载）
python main.py serve --reload

# 自定义端口
python main.py serve --port 8000
```

## API文档

### 统一API服务
- **端口**: 5001 (默认)
- **知识管理API文档**: [知识管理接口文档](./docs/知识管理接口.md)
- **知识分片接口文档**: [知识分片接口文档](./docs/知识分片接口.md)
- **Dify集成文档**: [Dify外部知识库API文档](./docs/Dify外部知识库API.md)
- **完整API信息**: 访问 `http://localhost:5001/` 获取所有可用端点和详细说明

### 可用端点概览
- **知识管理**: CRUD操作、语义搜索、向量检索
- **文档处理**: 上传、解析、分块处理
- **文本分块**: 直接文本智能分块
- **Dify集成**: 外部知识库API (`/retrieval`)
- **系统**: 健康检查、API文档

## 快速集成Dify

### Docker方式（推荐）
1. 启动完整服务：
```bash
docker-compose up -d --build
```

2. 在Dify平台中配置外部知识库：
   - API端点：`http://localhost:5001/retrieval`
   - API密钥：任意长度超过10位的字符串
   - 测试连接确认配置正确

### 本地方式
1. 启动API服务：
```bash
python main.py serve --host 0.0.0.0 --port 5001
```

2. 在Dify平台中配置外部知识库：
   - API端点：`http://your-server:5001/retrieval`
   - API密钥：任意长度超过10位的字符串
   - 测试连接确认配置正确

3. 开始在Dify中使用你的知识库！

## 项目结构

```
knowledge-database/
├── main.py                           # CLI入口
├── Dockerfile                        # Docker镜像构建文件
├── docker-compose.yml               # Docker Compose配置
├── pyproject.toml                   # Python项目配置
├── dify_kg_ext/
│   ├── api.py                       # 统一API（知识管理+Dify集成）
│   ├── dataclasses/                 # 数据模型
│   ├── es.py                        # Elasticsearch操作
│   ├── worker.py                    # Celery worker
│   └── adapters/                    # 适配器层
├── tests/                           # 测试文件
└── docs/
    ├── 知识管理接口.md               # 知识管理API文档
    ├── 知识分片接口.md               # 知识分片API文档
    └── Dify外部知识库API.md          # Dify API文档
```

## Docker环境变量配置

### 使用.env文件
所有Docker环境变量都可以通过`.env`文件配置：

```bash
# 复制示例文件
cp .env.example .env

# 编辑配置
nano .env
```

### 环境变量说明
| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `REDIS_HOST` | `redis` | Redis容器名称 |
| `REDIS_PORT` | `6379` | Redis服务端口 |
| `ELASTICSEARCH_HOST` | `elasticsearch` | Elasticsearch容器名称 |
| `ELASTICSEARCH_PORT` | `9200` | Elasticsearch服务端口 |
| `API_HOST` | `0.0.0.0` | API服务绑定地址 |
| `API_PORT` | `5001` | API服务端口 |
| `WORKER_CONCURRENCY` | `2` | Worker进程数 |
| `WORKER_LOG_LEVEL` | `info` | Worker日志级别 |
| `DATA_PATH` | `./data` | 数据目录挂载路径 |
| `ES_JAVA_OPTS` | `-Xms512m -Xmx512m` | Elasticsearch JVM内存设置 |
| `SMALL_MODEL_BACKEND` | `siliconflow` | 模型后端类型 |
| `SILICONFLOW_TOKEN` | - | SiliconFlow API令牌 |
| `DOCLING_ARTIFACTS_PATH` | `~/.cache/docling/models` | Docling模型缓存路径 |

### 自定义配置示例
```bash
# 修改端口避免冲突
API_PORT=8080
ELASTICSEARCH_PORT=9201
REDIS_PORT=6380

# 增加worker并发数
WORKER_CONCURRENCY=4

# 修改数据目录
DATA_PATH=/opt/knowledge-db/data
```

### 故障排除

#### Docker常见问题
1. **端口冲突**：修改`.env`文件中的端口配置
2. **内存不足**：调整`ES_JAVA_OPTS`参数，如`-Xms1g -Xmx1g`
3. **权限问题**：确保当前用户有Docker权限
4. **Redis连接失败**：检查Redis容器状态和网络配置

#### 日志查看
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f elasticsearch
docker-compose logs -f redis
```

#### 文档处理故障
- **文档解析失败**：检查SiliconFlow API令牌是否有效
- **处理超时**：增加worker并发数或检查文档大小
- **分块失败**：调整`chunk_token_count`参数

## 文档处理功能

系统提供完整的文档处理和文本分块功能：

### 文档处理流程
1. **上传文档**: 使用 `/upload_document` 端点上传文档
2. **异步处理**: 使用 `/analyzing_document` 端点触发异步解析
3. **获取结果**: 处理完成后获取分块结果
4. **直接分块**: 使用 `/chunk_text` 直接处理文本

### 支持的文档格式
- **PDF文档** (.pdf)
- **Word文档** (.docx, .doc)
- **文本文件** (.txt, .md)
- **PowerPoint** (.pptx)
- **Excel** (.xlsx)

### API使用示例

#### 1. 文档上传
```bash
curl -X POST "http://localhost:5001/upload_document" \
  -F "file=@example.pdf" \
  -F "dataset_id=my_dataset"
```

#### 2. 文档处理（异步）
```bash
curl -X POST "http://localhost:5001/analyzing_document" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_123456",
    "parser_config": {
      "chunk_token_count": 500,
      "page_size": 800
    }
  }'
```

#### 3. 直接文本分块
```bash
curl -X POST "http://localhost:5001/chunk_text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这里是长文本内容...",
    "chunk_token_count": 400
  }'
```

### 处理结果格式
```json
{
  "chunks": [
    {
      "content": "分块后的文本内容...",
      "metadata": {
        "chunk_index": 0,
        "token_count": 487,
        "page_number": 1,
        "start_offset": 0,
        "end_offset": 487
      }
    }
  ],
  "document_id": "doc_123456",
  "total_chunks": 5,
  "processing_time": 2.34
}
```

### 配置参数说明

#### Parser配置参数
| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `chunk_token_count` | integer | 500 | 每个分块的token数量 |
| `page_size` | integer | 800 | 页面大小限制 |

#### 高级用法示例
```python
# Python调用文档处理API
import requests

# 上传文档
files = {'file': open('document.pdf', 'rb')}
data = {'dataset_id': 'my_dataset'}
response = requests.post('http://localhost:5001/upload_document', files=files, data=data)
result = response.json()
document_id = result['document_id']

# 处理文档
process_data = {
    'document_id': document_id,
    'parser_config': {
        'chunk_token_count': 600,
        'page_size': 1000
    }
}
response = requests.post('http://localhost:5001/analyzing_document', json=process_data)
```
