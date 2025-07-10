# knowledge-database

语义科技智能体平台知识库

## 功能特性

- 🔍 语义搜索和向量检索
- 📚 知识库管理（增删改查）
- 🔗 知识点绑定和解绑
- 🤖 **Dify平台集成** - 提供Dify兼容的外部知识库API
- 📊 基于Elasticsearch的高性能搜索
- 🚀 FastAPI异步框架

## 环境要求
- Linux
- uv
- Elasticsearch
- Python 3.12+

## 安装和运行

### 安装依赖
```shell
uv sync
```

### 启动API服务（包含Dify集成）
```shell
python main.py serve --host 0.0.0.0 --port 5001
```

一个服务提供所有功能：
- 知识管理API (CRUD操作)
- Dify外部知识库API (`/retrieval`端点)
- 健康检查和API文档

### 启动文档处理Worker
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
- **Dify集成文档**: [Dify外部知识库API文档](./docs/Dify外部知识库API.md)
- **功能**: 
  - 知识库CRUD操作
  - Dify外部知识库集成
  - 语义搜索和向量检索

## 快速集成Dify

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
├── dify_kg_ext/
│   ├── entrypoints/
│   │   └── api.py                    # 统一API（知识管理+Dify集成）
│   ├── dataclasses.py               # 数据模型
│   ├── es.py                        # Elasticsearch操作
│   └── adapters/                    # 适配器层
├── examples/
│   └── test_dify_api.py             # Dify API测试脚本
└── docs/
    ├── 知识管理接口.md               # 知识管理API文档
    └── Dify外部知识库API.md          # Dify API文档
```
