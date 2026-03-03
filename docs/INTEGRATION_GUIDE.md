# HippoRAG 集成指南

本文档为第三方系统提供 HippoRAG 的集成指南，帮助您将 HippoRAG 的记忆增强检索能力集成到自己的应用中。

## 目录

- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [基础集成](#基础集成)
- [高级集成](#高级集成)
- [数据存储集成](#数据存储集成)
- [第三方系统集成示例](#第三方系统集成示例)
- [常见集成模式](#常见集成模式)
- [故障排除](#故障排除)

---

## 快速开始

### 1. 安装

```bash
pip install hipporag
```

### 2. 环境变量配置

```bash
export OPENAI_API_KEY=your_openai_api_key
export HF_HOME=/path/to/huggingface/cache  # 如果使用本地模型
```

### 3. 最简单的集成示例

```python
from hipporag import HippoRAG

# 初始化 HippoRAG
hipporag = HippoRAG(
    save_dir='./hipporag_data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)

# 索引文档
documents = ["您的文档内容1", "您的文档内容2", ...]
hipporag.index(docs=documents)

# 执行查询
results = hipporag.rag_qa(queries=["您的问题"])
print(results[0].answer)
```

---

## 核心概念

### HippoRAG 架构

HippoRAG 采用神经生物学启发的记忆框架，包含以下核心组件：

```
┌─────────────────────────────────────────────────────────────┐
│                     HippoRAG 系统架构                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  文档索引     │  │  知识图谱     │  │  嵌入存储     │       │
│  │  (Indexer)   │  │ (Graph)      │  │ (Embedding)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │                │
│         └─────────────────┴─────────────────┘                │
│                           │                                  │
│                   ┌───────────┐                             │
│                   │ 检索引擎   │                             │
│                   │(Retriever)│                             │
│                   └───────────┘                             │
│                           │                                  │
│                   ┌───────────┐                             │
│                   │ QA 引擎   │                             │
│                   │ (QAE)     │                             │
│                   └───────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

### 主要流程

1. **索引阶段**：将文档转化为知识图谱和嵌入向量
2. **检索阶段**：使用图算法（如 PPR）进行多跳检索
3. **问答阶段**：基于检索到的上下文生成答案

---

## 基础集成

### HippoRAG 类 API

#### 初始化

```python
from hipporag import HippoRAG

# 方式一：使用配置对象
from hipporag import BaseConfig
config = BaseConfig(
    save_dir='./data',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)
hipporag = HippoRAG(global_config=config)

# 方式二：直接传参
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)
```

#### 文档索引

```python
# 索引文档
documents = [
    "苹果公司是一家位于美国的科技公司",
    "蒂姆·库克是苹果公司的首席执行官",
    "iPhone 是苹果公司的主要产品"
]
hipporag.index(docs=documents)
```

#### 检索

```python
# 检索相关文档
queries = ["谁是苹果公司的CEO？"]
results = hipporag.retrieve(queries=queries, num_to_retrieve=5)

# 访问检索结果
for result in results:
    print(f"Query: {result.query}")
    for doc in result.retrieved_docs:
        print(f"  - {doc.content}")
```

#### 问答

```python
# 直接问答
results = hipporag.rag_qa(queries=["谁是苹果公司的CEO？"])
print(results[0].answer)

# 基于已有检索结果进行问答
retrieval_results = hipporag.retrieve(queries=queries, num_to_retrieve=5)
qa_results = hipporag.rag_qa(retrieval_results)
```

### 使用自定义 LLM 和 Embedding 端点

```python
# OpenAI 兼容端点
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='your-model-name',
    llm_base_url='https://your-llm-endpoint.com/v1',
    embedding_model_name='your-embedding-model',
    embedding_base_url='https://your-embedding-endpoint.com/v1'
)
```

---

## 高级集成

### 使用配置对象进行深度定制

```python
from hipporag import BaseConfig

config = BaseConfig(
    # 保存目录
    save_dir='./hipporag_data',

    # LLM 配置
    llm_name='gpt-4o-mini',
    llm_base_url=None,  # None 表示使用 OpenAI
    max_new_tokens=2048,
    temperature=0,
    max_retry_attempts=5,

    # Embedding 配置
    embedding_model_name='text-embedding-3-small',
    embedding_batch_size=16,
    embedding_max_seq_len=2048,

    # 检索配置
    retrieval_top_k=200,
    linking_top_k=5,
    damping=0.5,

    # QA 配置
    max_qa_steps=3,
    qa_top_k=5,

    # 图配置
    graph_library='igraph',  # 或 'dgraph'
    is_directed_graph=False,
    synonymy_edge_topk=2047,

    # 存储配置
    use_pgvector=False,  # 使用 PostgreSQL pgvector
)

hipporag = HippoRAG(global_config=config)
```

### 增量索引和删除

```python
# 增量索引
new_documents = ["新增的文档内容"]
hipporag.index(docs=new_documents)

# 删除文档
docs_to_delete = ["要删除的文档内容"]
hipporag.delete(docs_to_delete=docs_to_delete)
```

### 异步集成

HippoRAG 内部使用异步处理，您可以在异步环境中使用：

```python
import asyncio

async def async_query():
    hipporag = HippoRAG(
        save_dir='./data',
        llm_model_name='gpt-4o-mini',
        embedding_model_name='text-embedding-3-small'
    )

    # 索引操作
    await hipporag.index_async(docs=documents)

    # 查询操作
    results = await hipporag.rag_qa_async(queries=queries)
    return results

# 运行
results = asyncio.run(async_query())
```

---

## 数据存储集成

### 使用 PostgreSQL pgvector（推荐生产环境）

```python
config = BaseConfig(
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password',
    pgvector_index_type='hnsw',  # 或 'ivfflat'
    pgvector_index_lists=100
)

hipporag = HippoRAG(global_config=config)
```

**PostgreSQL 设置：**

```sql
-- 创建数据库
CREATE DATABASE hipporag;

-- 创建扩展
\c hipporag
CREATE EXTENSION vector;

-- 创建表（HippoRAG 会自动创建）
-- 表结构：
-- - chunks: 存储文档块
-- - entities: 存储实体
-- - facts: 存储事实三元组
```

### 使用 DGraph（分布式图数据库）

```python
config = BaseConfig(
    graph_library='dgraph',
    dgraph_config={
        'host': 'localhost',
        'port': 9080,
        'alpha_port': 9080,
        'zero_port': 5080
    }
)

hipporag = HippoRAG(global_config=config)
```

**DGraph 设置：**

```bash
# 使用 Docker 运行 DGraph
docker run -it -p 5080:5080 -p 9080:9080 -p 8080:8080 \
  -v ~/dgraph:/dgraph \
  dgraph/standalone:latest
```

---

## 第三方系统集成示例

### FastAPI Web 服务集成

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="HippoRAG API")

# 全局 HippoRAG 实例
hipporag = None

class IndexRequest(BaseModel):
    documents: List[str]

class QueryRequest(BaseModel):
    query: str
    num_to_retrieve: Optional[int] = 10

class QueryResponse(BaseModel):
    answer: str
    retrieved_docs: List[str]

@app.on_event("startup")
async def startup():
    global hipporag
    hipporag = HippoRAG(
        save_dir='./hipporag_data',
        llm_model_name='gpt-4o-mini',
        embedding_model_name='text-embedding-3-small'
    )

@app.post("/index")
async def index_documents(request: IndexRequest):
    """索引文档"""
    try:
        hipporag.index(docs=request.documents)
        return {"status": "success", "indexed": len(request.documents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """执行查询"""
    try:
        results = hipporag.rag_qa(queries=[request.query])
        return QueryResponse(
            answer=results[0].answer,
            retrieved_docs=[doc.content for doc in results[0].retrieved_docs]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Flask Web 服务集成

```python
from flask import Flask, request, jsonify
from hipporag import HippoRAG

app = Flask(__name__)

# 初始化 HippoRAG
hipporag = HippoRAG(
    save_dir='./hipporag_data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)

@app.route('/index', methods=['POST'])
def index():
    """索引文档"""
    data = request.json
    documents = data.get('documents', [])
    hipporag.index(docs=documents)
    return jsonify({"status": "success", "count": len(documents)})

@app.route('/query', methods=['POST'])
def query():
    """执行查询"""
    data = request.json
    query = data.get('query', '')
    results = hipporag.rag_qa(queries=[query])
    return jsonify({
        "answer": results[0].answer,
        "retrieved_docs": [doc.content for doc in results[0].retrieved_docs]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Django 集成

```python
# hipporag_app/services.py
from hipporag import HippoRAG
from django.conf import settings

class HippoRAGService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.hipporag = HippoRAG(
                save_dir=settings.HIPPORAG_SAVE_DIR,
                llm_model_name=getattr(settings, 'HIPPORAG_LLM_MODEL', 'gpt-4o-mini'),
                embedding_model_name=getattr(settings, 'HIPPORAG_EMBEDDING_MODEL', 'text-embedding-3-small')
            )
        return cls._instance

    def index_documents(self, documents):
        return self.hipporag.index(docs=documents)

    def query(self, question, num_retrieve=10):
        results = self.hipporag.rag_qa(queries=[question])
        return {
            "answer": results[0].answer,
            "retrieved_docs": [doc.content for doc in results[0].retrieved_docs]
        }

# hipporag_app/views.py
from django.http import JsonResponse
from .services import HippoRAGService

def index_view(request):
    if request.method == 'POST':
        documents = request.json.get('documents', [])
        HippoRAGService().index_documents(documents)
        return JsonResponse({"status": "success"})

def query_view(request):
    if request.method == 'POST':
        question = request.json.get('question')
        result = HippoRAGService().query(question)
        return JsonResponse(result)
```

### 数据库集成示例

```python
import psycopg2
from hipporag import HippoRAG

class DatabaseHippoRAG:
    def __init__(self, db_config, hipporag_config):
        # 初始化数据库连接
        self.conn = psycopg2.connect(**db_config)
        # 初始化 HippoRAG
        self.hipporag = HippoRAG(**hipporag_config)

    def sync_from_database(self, table_name, text_column):
        """从数据库同步文档到 HippoRAG"""
        with self.conn.cursor() as cursor:
            cursor.execute(f"SELECT {text_column} FROM {table_name}")
            documents = [row[0] for row in cursor.fetchall()]
        self.hipporag.index(docs=documents)

    def query_and_store(self, query):
        """查询并存储结果到数据库"""
        results = self.hipporag.rag_qa(queries=[query])
        # 存储逻辑...
        return results[0].answer
```

---

## 常见集成模式

### 模式 1: 文档管理集成

```python
class DocumentManager:
    def __init__(self, hipporag):
        self.hipporag = hipporag
        self.doc_index = {}  # 文档ID到内容的映射

    def add_document(self, doc_id: str, content: str):
        """添加文档"""
        self.doc_index[doc_id] = content
        self.hipporag.index(docs=[content])

    def update_document(self, doc_id: str, new_content: str):
        """更新文档"""
        if doc_id in self.doc_index:
            old_content = self.doc_index[doc_id]
            self.hipporag.delete(docs_to_delete=[old_content])
            self.doc_index[doc_id] = new_content
            self.hipporag.index(docs=[new_content])

    def delete_document(self, doc_id: str):
        """删除文档"""
        if doc_id in self.doc_index:
            content = self.doc_index[doc_id]
            self.hipporag.delete(docs_to_delete=[content])
            del self.doc_index[doc_id]
```

### 模式 2: 批量处理集成

```python
import queue
import threading

class BatchProcessor:
    def __init__(self, hipporag, batch_size=100):
        self.hipporag = hipporag
        self.batch_size = batch_size
        self.queue = queue.Queue()
        self.current_batch = []

    def add_document(self, doc: str):
        """添加文档到批处理队列"""
        self.queue.put(doc)
        self._maybe_process_batch()

    def _maybe_process_batch(self):
        """达到批次大小时处理"""
        if len(self.current_batch) >= self.batch_size:
            self.hipporag.index(docs=self.current_batch)
            self.current_batch = []

    def flush(self):
        """处理剩余的文档"""
        if self.current_batch:
            self.hipporag.index(docs=self.current_batch)
            self.current_batch = []
```

### 模式 3: 缓存集成

```python
import hashlib
import json
from functools import lru_cache

class CachedHippoRAG:
    def __init__(self, hipporag):
        self.hipporag = hipporag

    @lru_cache(maxsize=1000)
    def query(self, question: str):
        """带缓存的查询"""
        return self.hipporag.rag_qa(queries=[question])

    def _get_cache_key(self, question: str):
        """生成缓存键"""
        return hashlib.md5(question.encode()).hexdigest()

    def clear_cache(self):
        """清除缓存"""
        self.query.cache_clear()
```

---

## 故障排除

### 常见问题

#### 1. 索引速度慢

**原因**：LLM API 调用是主要瓶颈

**解决方案**：
- 使用批量处理增加 `embedding_batch_size`
- 使用更快的模型（如 `gpt-4o-mini` 而非 `gpt-4o`）
- 使用本地模型减少网络延迟

```python
config = BaseConfig(
    embedding_batch_size=32,  # 增加批次大小
    max_retry_attempts=3      # 减少重试次数
)
```

#### 2. 检索结果不相关

**原因**：检索参数配置不当

**解决方案**：
```python
config = BaseConfig(
    retrieval_top_k=500,    # 增加初始检索数量
    linking_top_k=10,      # 增加链接节点数量
    damping=0.7,           # 调整阻尼因子
    max_qa_steps=3         # 增加推理步骤
)
```

#### 3. 内存不足

**原因**：图过大，使用内存存储

**解决方案**：
- 使用 PostgreSQL pgvector 存储嵌入
- 使用 DGraph 存储图
- 减少文档集大小

```python
config = BaseConfig(
    use_pgvector=True,
    graph_library='dgraph'
)
```

#### 4. API 调用失败

**原因**：网络问题或 API 限流

**解决方案**：
```python
config = BaseConfig(
    max_retry_attempts=10,     # 增加重试次数
    llm_base_url='your_proxy_url'  # 使用代理
)
```

### 日志和调试

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

# 查看配置
hipporag = HippoRAG(global_config=config)
print(hipporag.global_config)
```

---

## 更多资源

- [API 参考文档](./API_REFERENCE.md)
- [配置指南](./CONFIGURATION.md)
- [部署指南](./DEPLOYMENT.md)
- [GitHub 仓库](https://github.com/OSU-NLP-Group/HippoRAG)
- [论文](https://arxiv.org/abs/2502.14802)

---

## 联系与支持

如有问题或建议，请：
- 提交 [GitHub Issue](https://github.com/OSU-NLP-Group/HippoRAG/issues)
- 联系：hipporag@osu.edu
