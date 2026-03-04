# HippoRAG 多业务多书籍架构设计

## 1. 概述

### 1.1 需求背景

HippoRAG 需要支持多业务（多租户）场景：
- **书籍 (Book)**: 独立的数据单元，索引一次，可被多个业务共享
- **业务 (Business)**: 书籍的集合视图，查询按业务维度进行

### 1.2 核心概念

| 概念 | 说明 | 特点 |
|------|------|------|
| `book_id` | 书籍标识，数据隔离的最小单元 | 索引时指定，一本书只索引一次 |
| `business_id` | 业务标识，代表一个租户/客户 | 查询时指定，可访问绑定的多本书 |

### 1.3 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  POST /book/index   POST /business/qa   POST /business/retrieve  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Books (独立存储)                            │
│                                                                 │
│  Book 1 ──► DGraph + pgvector (book_id=book_001)               │
│  Book 2 ──► DGraph + pgvector (book_id=book_002)               │
│  Book 3 ──► DGraph + pgvector (book_id=book_003)               │
│                                                                 │
│  书籍只索引一次，可被多个业务共享                                  │
│  注: pgvector 按 book_id 隔离，DGraph 共享                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ book_bindings 表
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Business (业务视图)                            │
│                                                                 │
│  Business A ──► [Book 1, Book 2]                                │
│  Business B ──► [Book 2, Book 3]  ◄── 共享 Book 2               │
│  Business C ──► [Book 1, Book 3]                                │
│                                                                 │
│  查询时按 business_id 搜索其绑定的所有 books                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. API 设计

### 2.1 书籍索引接口 (按 book 维度)

#### `POST /book/index/sync`

同步索引文档到指定书籍。

**请求：**
```json
{
  "book_id": "novel_001",
  "docs": [
    "第一章：方源一身残破的碧绿大袍...",
    "第二章：山风吹得血袍飘荡..."
  ]
}
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

### 2.2 业务绑定接口

#### `POST /business/bind`

将书籍绑定到业务。

**请求：**
```json
{
  "business_id": "company_001",
  "book_ids": ["novel_001", "novel_002"]
}
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

### 2.3 业务查询接口 (按 business 维度)

#### `POST /business/qa`

按业务维度进行问答（搜索该业务绑定的所有书籍）。

**请求：**
```json
{
  "business_id": "company_001",
  "queries": ["方源穿的是什么颜色的袍子？"]
}
```

**响应：**
```json
{
  "results": [
    {
      "query": "方源穿的是什么颜色的袍子？",
      "answer": "碧绿",
      "book_id": "novel_001",
      "passages": [
        {"content": "方源一身残破的碧绿大袍...", "doc_id": null, "book_id": "novel_001"}
      ]
    }
  ],
  "business_id": "company_001",
  "books_searched": ["novel_001"]
}
```

#### `POST /business/retrieve`

按业务维度进行检索。

**请求：**
```json
{
  "business_id": "company_001",
  "queries": ["方源的特点"],
  "num_to_retrieve": 10,
  "return_scores": true
}
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
  "books_searched": ["novel_001"]
}
```

### 2.4 管理接口

#### `GET /business/books`

列出业务绑定的所有书籍。

**请求：**
```
GET /business/books?business_id=company_001
```

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
    },
    {
      "book_id": "novel_002",
      "doc_count": 50,
      "status": "ready",
      "created_at": "2026-03-04T11:00:00Z",
      "updated_at": "2026-03-04T11:00:00Z"
    }
  ]
}
```

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

#### `DELETE /book`

删除书籍及其所有数据（会解除所有业务绑定）。

**请求：**
```
DELETE /book?book_id=novel_001
```

**响应：**
```json
{
  "status": "completed",
  "message": "Book novel_001 deleted"
}
```

---

## 3. 数据库设计

### 3.1 书籍绑定表 (book_bindings)

```sql
CREATE TABLE book_bindings (
    id SERIAL PRIMARY KEY,
    business_id VARCHAR(64) NOT NULL,
    book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(business_id, book_id)
);

CREATE INDEX idx_book_bindings_business ON book_bindings(business_id);
CREATE INDEX idx_book_bindings_book ON book_bindings(book_id);
```

**示例数据：**
```
| business_id  | book_id     |
|--------------|-------------|
| company_001  | novel_001   |
| company_001  | novel_002   |
| company_002  | novel_002   |  <-- 共享 novel_002
| company_002  | novel_003   |
```

### 3.2 书籍元数据表 (books)

```sql
CREATE TABLE books (
    book_id VARCHAR(64) PRIMARY KEY,
    doc_count INT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'ready',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3.3 嵌入表修改 (embeddings)

在现有 embeddings 表添加 book_id 列：

```sql
-- 在现有 embeddings 表添加 book_id
ALTER TABLE embeddings_chunk ADD COLUMN book_id VARCHAR(64);
ALTER TABLE embeddings_entity ADD COLUMN book_id VARCHAR(64);
ALTER TABLE embeddings_fact ADD COLUMN book_id VARCHAR(64);

CREATE INDEX idx_embeddings_chunk_book ON embeddings_chunk(book_id);
CREATE INDEX idx_embeddings_entity_book ON embeddings_entity(book_id);
CREATE INDEX idx_embeddings_fact_book ON embeddings_fact(book_id);
```

### 3.4 DGraph 数据隔离

当前实现中，DGraph 数据在所有书籍间共享。嵌入数据通过 book_id 在 PostgreSQL 中隔离。

未来可考虑为每个 book 使用独立的 predicate 前缀：

```
原始 predicate:     entity, fact, passage
带前缀 predicate:   book_{book_id}__entity
                    book_{book_id}__fact
                    book_{book_id}__passage

示例:
book_novel_001__entity
book_novel_001__fact
book_novel_001__passage
```

---

## 4. 代码结构

### 4.1 新增文件

```
src/hipporag/
├── multi_tenancy/
│   ├── __init__.py         # 模块入口
│   ├── database.py         # 数据库操作 (book_bindings, books)
│   └── manager.py          # 多租户管理器
├── api/
│   ├── models.py           # 新增请求/响应模型
│   ├── routes.py           # 新增路由端点
│   └── dependencies.py     # 新增 MultiTenancyManager
```

### 4.2 修改文件

- `src/hipporag/utils/config_utils.py` - 添加 `book_id` 配置
- `src/hipporag/embedding_store.py` - 传递 `book_id` 到 PgVectorEmbeddingStore
- `src/hipporag/embedding_store_pgvector.py` - 支持 `book_id` 过滤

---

## 5. 请求/响应模型

```python
# 书籍索引
class BookIndexRequest(BaseModel):
    book_id: str
    docs: List[str]

# 业务绑定
class BusinessBindRequest(BaseModel):
    business_id: str
    book_ids: List[str]

class BusinessUnbindRequest(BaseModel):
    business_id: str
    book_ids: List[str]

# 业务查询
class BusinessQARequest(BaseModel):
    business_id: str
    queries: List[str]
    num_to_retrieve: Optional[int] = None

class BusinessRetrieveRequest(BaseModel):
    business_id: str
    queries: List[str]
    num_to_retrieve: Optional[int] = None
    return_scores: bool = False

# 响应
class BookIndexResponse(BaseModel):
    status: str
    message: str
    book_id: str
    num_docs: int

class BookInfo(BaseModel):
    book_id: str
    doc_count: int
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]

class BusinessQAResult(BaseModel):
    query: str
    answer: str
    passages: List[BusinessPassage]
    book_id: Optional[str]

class BusinessQAResponse(BaseModel):
    results: List[BusinessQAResult]
    business_id: str
    books_searched: List[str]
```

---

## 6. 核心逻辑

### 6.1 索引流程 (按 book)

```python
def index_book(book_id: str, docs: List[str]):
    # 1. 创建/获取该书的 HippoRAG 实例
    hipporag = get_or_create_book_instance(book_id)

    # 2. 配置中设置 book_id，用于 embedding 隔离
    config.book_id = book_id

    # 3. 索引文档
    hipporag.index(docs=docs)

    # 4. 更新 books 表元数据
    db.update_book_doc_count(book_id, len(docs))
```

### 6.2 查询流程 (按 business)

```python
def query_business(business_id: str, queries: List[str]):
    # 1. 从 book_bindings 表查询该业务绑定的所有 book_ids
    book_ids = db.get_book_ids_by_business(business_id)

    # 2. 并行检索每本书
    all_results = []
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(retrieve_from_book, book_id, queries)
            for book_id in book_ids
        ]
        for future in as_completed(futures):
            all_results.extend(future.result())

    # 3. 合并结果
    merged = merge_results(all_results)

    return merged
```

---

## 7. 测试场景

### 7.1 数据准备

```
Book novel_001: 索引 "方源穿碧绿大袍"
Book novel_002: 索引 "张三穿红色衣服"
Book novel_003: 索引 "李四穿蓝色衣服"

Business A 绑定: [novel_001, novel_002]
Business B 绑定: [novel_002, novel_003]
```

### 7.2 预期结果

| 查询条件 | 预期答案 | 说明 |
|----------|----------|------|
| Business A, "穿什么颜色？" | 碧绿 / 红色 | 搜索 novel_001 + novel_002 |
| Business B, "穿什么颜色？" | 红色 / 蓝色 | 搜索 novel_002 + novel_003 |
| Business A, "李四穿什么？" | 无结果 | novel_003 未绑定到 A |
| Business B, "方源穿什么？" | 无结果 | novel_001 未绑定到 B |

---

## 8. API 汇总

| 方法 | 端点 | 说明 | 维度 |
|------|------|------|------|
| POST | `/book/index/sync` | 索引文档 | book |
| POST | `/business/bind` | 绑定书籍到业务 | business-book |
| POST | `/business/unbind` | 解除绑定 | business-book |
| GET | `/business/books` | 列出业务书籍 | business |
| POST | `/business/qa` | 问答 | business |
| POST | `/business/retrieve` | 检索 | business |
| GET | `/books` | 列出所有书籍 | - |
| DELETE | `/book` | 删除书籍 | book |

---

## 9. 实现状态

| 功能 | 状态 | 说明 |
|------|------|------|
| book_bindings 表 | ✅ 完成 | 核心多对多关系 |
| books 表 | ✅ 完成 | 书籍元数据 |
| embeddings 表添加 book_id | ✅ 完成 | 数据隔离 |
| /book/index/sync | ✅ 完成 | 按书籍索引 |
| /business/bind | ✅ 完成 | 绑定管理 |
| /business/unbind | ✅ 完成 | 解除绑定 |
| /business/qa | ✅ 完成 | 按业务查询 |
| /business/retrieve | ✅ 完成 | 按业务检索 |
| /business/books | ✅ 完成 | 列出业务书籍 |
| /books | ✅ 完成 | 列出所有书籍 |
| DELETE /book | ✅ 完成 | 删除书籍 |
| DGraph 命名空间隔离 | 🔄 待实现 | 当前 DGraph 共享 |
