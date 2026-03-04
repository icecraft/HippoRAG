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
