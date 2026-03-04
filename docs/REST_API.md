# HippoRAG REST API 文档

本文档详细介绍 HippoRAG 的 RESTful API 接口，帮助第三方系统通过 HTTP API 集成。

## 快速开始

### 1. 配置环境变量

创建 `.env` 文件：

```bash
# API Key
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1

# 模型配置
HIPPORAG_LLM_MODEL=gpt-4o-mini
HIPPORAG_EMBEDDING_MODEL=text-embedding-3-small

# DGraph 连接
DGRAPH_GRPC=localhost:9080

# pgvector 配置
USE_PGVECTOR=true
PGVECTOR_HOST=localhost
PGVECTOR_PORT=5432
PGVECTOR_DATABASE=hipporag
PGVECTOR_USER=postgres
PGVECTOR_PASSWORD=your_password
```

### 2. 启动服务

```bash
# 设置 PYTHONPATH
export PYTHONPATH=/path/to/HippoRAG/src:$PYTHONPATH

# 加载环境变量
source .env  # 或 export $(cat .env | xargs)

# 启动服务
uvicorn hipporag.api:app --host 0.0.0.0 --port 8000
```

### 3. 验证服务

```bash
curl http://localhost:8000/health
```

---

## API 端点

### 基础端点

#### `GET /`
获取 API 基本信息。

#### `GET /health`
健康检查。

**响应示例：**
```json
{
  "status": "healthy",
  "hipporag_initialized": true,
  "indexing_status": "idle"
}
```

#### `GET /status`
获取索引进度。

---

### 索引端点

#### `POST /index`
异步索引文档（立即返回，后台处理）。

**请求：**
```json
{
  "docs": ["文档1", "文档2"]
}
```

**响应：**
```json
{
  "status": "accepted",
  "message": "Started indexing 2 documents in background",
  "num_docs": 2
}
```

#### `POST /index/sync`
同步索引文档（等待完成）。

**请求：**
```json
{
  "docs": ["文档1", "文档2"]
}
```

**响应：**
```json
{
  "status": "completed",
  "message": "Successfully indexed 2 documents",
  "num_docs": 2
}
```

---

### 检索端点

#### `POST /retrieve`
HippoRAG 图检索（多跳推理）。

**请求：**
```json
{
  "queries": ["查询问题"],
  "num_to_retrieve": 10,
  "return_scores": true
}
```

**响应：**
```json
{
  "results": [
    {
      "query": "查询问题",
      "passages": [
        {"content": "相关段落...", "doc_id": null}
      ],
      "scores": [0.95]
    }
  ],
  "metrics": null
}
```

#### `POST /retrieve/dpr`
标准 DPR 检索（向量相似度）。

---

### 问答端点

#### `POST /qa`
HippoRAG 图检索 + LLM 问答。

**请求：**
```json
{
  "queries": ["问题"],
  "num_to_retrieve": 5
}
```

**响应：**
```json
{
  "results": [
    {
      "query": "问题",
      "answer": "生成的答案...",
      "passages": [
        {"content": "支持段落...", "doc_id": null}
      ]
    }
  ],
  "metrics": null
}
```

#### `POST /qa/dpr`
DPR 检索 + LLM 问答。

---

## 使用示例

### cURL

```bash
# 索引
curl -X POST http://localhost:8000/index/sync \
  -H "Content-Type: application/json" \
  -d '{"docs": ["Python 是编程语言", "Python 由 Guido 创建"]}'

# 问答
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"queries": ["Python 是谁创建的？"]}'

# 检索
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"queries": ["Python 用途"], "num_to_retrieve": 5}'
```

### Python

```python
import requests

API_URL = "http://localhost:8000"

# 索引文档
requests.post(f"{API_URL}/index/sync", json={
    "docs": ["文档内容"]
})

# 问答
response = requests.post(f"{API_URL}/qa", json={
    "queries": ["问题"]
})
result = response.json()
print(result["results"][0]["answer"])

# 检索
response = requests.post(f"{API_URL}/retrieve", json={
    "queries": ["查询"],
    "num_to_retrieve": 5
})
for passage in response.json()["results"][0]["passages"]:
    print(passage["content"])
```

### JavaScript

```javascript
const API_URL = 'http://localhost:8000';

// 索引
await fetch(`${API_URL}/index/sync`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ docs: ['文档内容'] })
});

// 问答
const response = await fetch(`${API_URL}/qa`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ queries: ['问题'] })
});
const result = await response.json();
console.log(result.results[0].answer);
```

---

## 客户端工具

项目提供命令行客户端：

```bash
# 索引
python projects/ingest_via_api.py --chapters_file docs.json --api_url http://localhost:8000

# 交互式查询
python projects/query_via_api.py --interactive --api_url http://localhost:8000

# 单次查询
python projects/query_via_api.py --query "问题" --api_url http://localhost:8000
```

---

## 交互式文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | - | API 密钥（必需） |
| `OPENAI_BASE_URL` | - | 统一 API 端点 |
| `HIPPORAG_LLM_MODEL` | `gpt-4o-mini` | LLM 模型 |
| `HIPPORAG_EMBEDDING_MODEL` | `text-embedding-3-small` | 嵌入模型 |
| `DGRAPH_GRPC` | `localhost:9080` | DGraph 地址 |
| `USE_PGVECTOR` | `true` | 使用 pgvector |
| `PGVECTOR_HOST` | `localhost` | PostgreSQL 主机 |
| `PGVECTOR_PORT` | `5432` | PostgreSQL 端口 |
| `PGVECTOR_DATABASE` | `hipporag` | 数据库名 |
| `PGVECTOR_USER` | `postgres` | 用户名 |
| `PGVECTOR_PASSWORD` | `""` | 密码 |
| `EMBEDDING_BATCH_SIZE` | `10` | 嵌入批处理大小 |

---

## 更多资源

- [集成指南](./INTEGRATION_GUIDE.md)
- [API 参考文档](./API_REFERENCE.md)
- [部署指南](./DEPLOYMENT.md)
