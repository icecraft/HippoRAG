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
# {"status": "healthy", "hipporag_initialized": true, "indexing_status": "idle"}
```

---

## API 端点

### 基础端点

#### `GET /health`
健康检查。

**测试响应：**
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

#### `POST /index/sync`
同步索引文档（等待完成）。

**测试请求：**
```bash
curl -X POST http://localhost:8000/index/sync \
  -H "Content-Type: application/json" \
  -d '{
    "docs": ["方源一身残破的碧绿大袍，披头散发，浑身浴血，环顾四周。山风吹得血袍飘荡，如战旗般嚯嚯作响。就这样紧张地对峙了三个时辰，夕阳西下。他本是地球上的华夏学子，机缘巧合穿越到这方世界。"]
  }'
```

**测试响应：**
```json
{
  "status": "completed",
  "message": "Successfully indexed 1 documents",
  "num_docs": 1
}
```

---

### 问答端点

#### `POST /qa`
HippoRAG 图检索 + LLM 问答。

**测试请求：**
```bash
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"queries": ["方源身上穿的是什么颜色的袍子？"], "num_to_retrieve": 3}'
```

**测试响应：**
```json
{
  "results": [
    {
      "query": "方源身上穿的是什么颜色的袍子？",
      "answer": "碧绿 (green)",
      "passages": [
        {"content": "方源一身残破的碧绿大袍，披头散发，浑身浴血，环顾四周...", "doc_id": null}
      ]
    }
  ],
  "metrics": null
}
```

**更多测试示例：**

| 问题 | 答案 | 来源 |
|------|------|------|
| 方源身上穿的是什么颜色的袍子？ | **碧绿 (green)** | "方源一身残破的**碧绿**大袍" |
| 方源被困了多长时间？ | **三个时辰** | "就这样紧张地对峙了**三个时辰**" |
| 方源来自哪里？ | **Earth** | "他本是**地球**上的华夏学子" |

---

### 检索端点

#### `POST /retrieve`
HippoRAG 图检索（多跳推理）。

**测试请求：**
```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"queries": ["方源的特点"], "num_to_retrieve": 5, "return_scores": true}'
```

**测试响应：**
```json
{
  "results": [
    {
      "query": "方源的特点",
      "passages": [
        {"content": "方源一身残破的碧绿大袍，披头散发，浑身浴血...", "doc_id": null}
      ],
      "scores": [0.85]
    }
  ],
  "metrics": null
}
```

#### `POST /retrieve/dpr`
标准 DPR 检索（向量相似度）。

#### `POST /qa/dpr`
DPR 检索 + LLM 问答。

---

## 多租户端点（Multi-Tenancy）

多租户功能支持按书籍（Book）维度索引数据，按业务（Business）维度查询。

### 核心概念

| 概念 | 说明 |
|------|------|
| `book_id` | 书籍标识，数据隔离的最小单元，索引一次，可被多个业务共享 |
| `business_id` | 业务标识，代表一个租户，可访问绑定的多本书 |

### 书籍索引

#### `POST /book/index/sync`
同步索引文档到指定书籍。

**请求：**
```bash
curl -X POST http://localhost:8000/book/index/sync \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "novel_001",
    "docs": [
      "方源一身残破的碧绿大袍，披头散发，浑身浴血。",
      "就这样紧张地对峙了三个时辰，夕阳西下。"
    ]
  }'
```

**响应：**
```json
{
  "status": "completed",
  "message": "Successfully indexed 2 documents",
  "book_id": "novel_001",
  "num_docs": 2
}
```

### 书籍管理

#### `GET /books`
列出所有书籍。

**响应：**
```json
{
  "books": [
    {
      "book_id": "novel_001",
      "doc_count": 100,
      "status": "ready",
      "created_at": "2026-03-04T10:00:00Z",
      "updated_at": "2026-03-04T10:00:00Z"
    }
  ]
}
```

#### `DELETE /book?book_id={book_id}`
删除书籍及其所有数据。

**响应：**
```json
{
  "status": "completed",
  "message": "Book novel_001 deleted"
}
```

### 业务绑定

#### `POST /business/bind`
将书籍绑定到业务。

**请求：**
```bash
curl -X POST http://localhost:8000/business/bind \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "company_001",
    "book_ids": ["novel_001", "novel_002"]
  }'
```

**响应：**
```json
{
  "status": "completed",
  "message": "Successfully bound 2 books to business",
  "business_id": "company_001",
  "book_ids": ["novel_001", "novel_002"]
}
```

#### `POST /business/unbind`
解除书籍与业务的绑定。

**请求：**
```json
{
  "business_id": "company_001",
  "book_ids": ["novel_002"]
}
```

#### `GET /business/books?business_id={business_id}`
列出业务绑定的所有书籍。

**响应：**
```json
{
  "business_id": "company_001",
  "books": [
    {
      "book_id": "novel_001",
      "doc_count": 100,
      "status": "ready",
      "created_at": "2026-03-04T10:00:00Z",
      "updated_at": "2026-03-04T10:00:00Z"
    }
  ]
}
```

### 业务管理

#### `POST /business`
创建新的业务记录。

**请求：**
```bash
curl -X POST http://localhost:8000/business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "company_001",
    "name": "示例公司",
    "description": "这是一个示例业务"
  }'
```

**响应：**
```json
{
  "status": "created",
  "message": "Business company_001 created successfully",
  "business_id": "company_001"
}
```

#### `GET /business/{business_id}`
获取业务信息。

**响应：**
```json
{
  "business_id": "company_001",
  "name": "示例公司",
  "description": "这是一个示例业务",
  "book_count": 2,
  "status": "active",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T10:00:00Z"
}
```

#### `GET /businesses`
列出所有业务。

**响应：**
```json
{
  "businesses": [
    {
      "business_id": "company_001",
      "name": "示例公司",
      "description": "这是一个示例业务",
      "book_count": 2,
      "status": "active",
      "created_at": "2026-03-04T10:00:00Z",
      "updated_at": "2026-03-04T10:00:00Z"
    }
  ]
}
```

#### `PUT /business/{business_id}`
更新业务信息。

**请求：**
```bash
curl -X PUT http://localhost:8000/business/company_001 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "新公司名称",
    "description": "更新后的描述"
  }'
```

**响应：**
```json
{
  "status": "updated",
  "message": "Business company_001 updated successfully",
  "business_id": "company_001"
}
```

#### `DELETE /business/{business_id}`
删除业务及其所有绑定关系。

**响应：**
```json
{
  "status": "deleted",
  "message": "Business company_001 deleted successfully"
}
```

### 书籍管理

#### `POST /book`
创建新的书籍记录（不索引文档）。

**请求：**
```bash
curl -X POST http://localhost:8000/book \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "novel_001"
  }'
```

**响应：**
```json
{
  "status": "created",
  "message": "Book novel_001 created successfully",
  "book_id": "novel_001"
}
```

### 业务查询

#### `POST /business/qa`
按业务维度进行问答（搜索该业务绑定的所有书籍）。

**请求：**
```bash
curl -X POST http://localhost:8000/business/qa \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "company_001",
    "queries": ["方源穿的是什么颜色的袍子？"]
  }'
```

**响应：**
```json
{
  "results": [
    {
      "query": "方源穿的是什么颜色的袍子？",
      "answer": "碧绿",
      "passages": [
        {"content": "方源一身残破的碧绿大袍...", "doc_id": null, "book_id": "novel_001"}
      ],
      "book_id": "novel_001"
    }
  ],
  "business_id": "company_001",
  "books_searched": ["novel_001", "novel_002"]
}
```

#### `POST /business/retrieve`
按业务维度进行检索。

**请求：**
```bash
curl -X POST http://localhost:8000/business/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "company_001",
    "queries": ["方源的特点"],
    "num_to_retrieve": 10,
    "return_scores": true
  }'
```

**响应：**
```json
{
  "results": [
    {
      "query": "方源的特点",
      "passages": [
        {"content": "方源一身残破的碧绿大袍...", "doc_id": null, "book_id": "novel_001"}
      ],
      "scores": [0.85]
    }
  ],
  "business_id": "company_001",
  "books_searched": ["novel_001", "novel_002"]
}
```

---

## 多租户完整示例

### Python 示例

```python
import requests

API_URL = "http://localhost:8000"

# 1. 索引多本书籍
print("=== 索引书籍 ===")
books = {
    "novel_001": ["方源一身残破的碧绿大袍，披头散发，浑身浴血。"],
    "novel_002": ["张三穿着一件红色的长袍，站在城门口。"],
    "novel_003": ["李四穿着蓝色的衣服，坐在茶馆里。"]
}

for book_id, docs in books.items():
    response = requests.post(f"{API_URL}/book/index/sync", json={
        "book_id": book_id,
        "docs": docs
    })
    print(f"  {book_id}: {response.json()['status']}")

# 2. 绑定书籍到业务
print("\n=== 绑定业务 ===")
# Business A 可以访问 novel_001 和 novel_002
requests.post(f"{API_URL}/business/bind", json={
    "business_id": "business_a",
    "book_ids": ["novel_001", "novel_002"]
})
print("  Business A: novel_001, novel_002")

# Business B 可以访问 novel_002 和 novel_003
requests.post(f"{API_URL}/business/bind", json={
    "business_id": "business_b",
    "book_ids": ["novel_002", "novel_003"]
})
print("  Business B: novel_002, novel_003")

# 3. 业务查询（验证数据隔离）
print("\n=== 业务查询测试 ===")
query = "方源穿的是什么颜色的袍子？"

# Business A 查询（能找到方源的信息）
response = requests.post(f"{API_URL}/business/qa", json={
    "business_id": "business_a",
    "queries": [query]
})
result = response.json()
print(f"  Business A: {result['results'][0]['answer']}")

# Business B 查询（找不到方源的信息，因为 novel_001 未绑定）
response = requests.post(f"{API_URL}/business/qa", json={
    "business_id": "business_b",
    "queries": [query]
})
result = response.json()
print(f"  Business B: {result['results'][0]['answer']}")
```

**输出：**
```
=== 索引书籍 ===
  novel_001: completed
  novel_002: completed
  novel_003: completed

=== 绑定业务 ===
  Business A: novel_001, novel_002
  Business B: novel_002, novel_003

=== 业务查询测试 ===
  Business A: 碧绿 (green)
  Business B: 没有找到关于方源的信息
```

---

## API 端点汇总

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/status` | 索引进度 |
| **索引** | | |
| POST | `/index` | 异步索引文档 |
| POST | `/index/sync` | 同步索引文档 |
| **检索** | | |
| POST | `/retrieve` | HippoRAG 图检索 |
| POST | `/retrieve/dpr` | DPR 向量检索 |
| POST | `/qa` | HippoRAG 问答 |
| POST | `/qa/dpr` | DPR 问答 |
| **书籍管理** | | |
| POST | `/book` | 创建书籍记录 |
| POST | `/book/index/sync` | 按书籍索引文档 |
| GET | `/books` | 列出所有书籍 |
| DELETE | `/book` | 删除书籍 |
| **业务管理** | | |
| POST | `/business` | 创建业务记录 |
| GET | `/businesses` | 列出所有业务 |
| GET | `/business/{business_id}` | 获取业务信息 |
| PUT | `/business/{business_id}` | 更新业务信息 |
| DELETE | `/business/{business_id}` | 删除业务 |
| POST | `/business/bind` | 绑定书籍到业务 |
| POST | `/business/unbind` | 解除绑定 |
| GET | `/business/books` | 列出业务书籍 |
| **业务查询** | | |
| POST | `/business/qa` | 按业务问答 |
| POST | `/business/retrieve` | 按业务检索 |

---

## 完整使用示例

### Python 完整示例

```python
import requests

API_URL = "http://localhost:8000"

# 1. 索引文档
print("=== 索引文档 ===")
docs = [
    "方源一身残破的碧绿大袍，披头散发，浑身浴血，环顾四周。",
    "就这样紧张地对峙了三个时辰，夕阳西下。",
    "他本是地球上的华夏学子，机缘巧合穿越到这方世界。"
]
response = requests.post(f"{API_URL}/index/sync", json={"docs": docs})
print(f"状态: {response.json()['status']}")
print(f"消息: {response.json()['message']}")
# 输出: 状态: completed
#       消息: Successfully indexed 3 documents

# 2. 问答
print("\n=== 问答测试 ===")
questions = [
    "方源身上穿的是什么颜色的袍子？",
    "方源被困了多长时间？",
    "方源来自哪里？"
]
for q in questions:
    response = requests.post(f"{API_URL}/qa", json={"queries": [q], "num_to_retrieve": 3})
    result = response.json()
    print(f"Q: {q}")
    print(f"A: {result['results'][0]['answer']}")
    print()

# 3. 检索
print("=== 检索测试 ===")
response = requests.post(f"{API_URL}/retrieve", json={
    "queries": ["方源的外貌"],
    "num_to_retrieve": 3,
    "return_scores": True
})
for i, p in enumerate(response.json()["results"][0]["passages"], 1):
    print(f"[{i}] {p['content'][:50]}...")
```

**输出：**
```
=== 索引文档 ===
状态: completed
消息: Successfully indexed 3 documents

=== 问答测试 ===
Q: 方源身上穿的是什么颜色的袍子？
A: 碧绿 (green)

Q: 方源被困了多长时间？
A: 三个时辰

Q: 方源来自哪里？
A: Earth

=== 检索测试 ===
[1] 方源一身残破的碧绿大袍，披头散发，浑身浴血...
```

### cURL 完整示例

```bash
# 索引
curl -X POST http://localhost:8000/index/sync \
  -H "Content-Type: application/json" \
  -d '{"docs": ["文档内容"]}'

# 问答
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"queries": ["问题"], "num_to_retrieve": 5}'

# 检索
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"queries": ["查询"], "num_to_retrieve": 5, "return_scores": true}'
```

### JavaScript 示例

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
- [多租户设计文档](./MULTI_TENANCY_DESIGN.md)
