# HippoRAG API 参考文档

本文档详细介绍了 HippoRAG 的核心 API 接口。

## 目录

- [HippoRAG 类](#hipporag-类)
- [BaseConfig 类](#baseconfig-类)
- [数据类型](#数据类型)
- [工具函数](#工具函数)

---

## HippoRAG 类

HippoRAG 是主要的 API 入口类，提供文档索引、检索和问答功能。

### 构造函数

```python
HippoRAG(
    global_config: BaseConfig = None,
    save_dir: str = None,
    llm_model_name: str = None,
    llm_base_url: str = None,
    embedding_model_name: str = None,
    embedding_base_url: str = None,
    azure_endpoint: str = None,
    azure_embedding_endpoint: str = None
)
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `global_config` | `BaseConfig` | `None` | 全局配置对象 |
| `save_dir` | `str` | `'outputs'` | 数据保存目录 |
| `llm_model_name` | `str` | `'gpt-4o-mini'` | LLM 模型名称 |
| `llm_base_url` | `str` | `None` | LLM API 端点 URL |
| `embedding_model_name` | `str` | `'text-embedding-3-small'` | 嵌入模型名称 |
| `embedding_base_url` | `str` | `None` | 嵌入 API 端点 URL |
| `azure_endpoint` | `str` | `None` | Azure OpenAI 端点 |
| `azure_embedding_endpoint` | `str` | `None` | Azure 嵌入端点 |

**示例**：

```python
from hipporag import HippoRAG

# 简单初始化
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)

# 使用自定义端点
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='custom-model',
    llm_base_url='https://api.example.com/v1',
    embedding_model_name='custom-embedding',
    embedding_base_url='https://api.example.com/v1'
)

# 使用 Azure
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='gpt-4o-mini',
    azure_endpoint='https://your-resource.openai.azure.com/',
    azure_embedding_endpoint='https://your-resource.openai.azure.com/'
)
```

---

### 方法

#### `index()`

索引文档，构建知识图谱和嵌入向量。

```python
index(docs: List[str], progress_callback: Callable[[str, int, int], None] = None) -> None
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `docs` | `List[str]` | 要索引的文档列表 |
| `progress_callback` | `Callable[[stage, current, total], None]` | 可选的进度回调函数 |

**进度阶段（stage）**：

| 阶段 | 说明 |
|------|------|
| `embedding_chunks` | 文档嵌入 |
| `openie` | 实体与关系抽取 |
| `embedding_entities` | 实体嵌入 |
| `embedding_facts` | 事实嵌入 |
| `graph_construction` | 知识图谱构建 |
| `completed` | 完成 |

**示例**：

```python
documents = [
    "苹果公司成立于1976年",
    "史蒂夫·乔布斯是苹果公司的联合创始人"
]

# 基本用法
hipporag.index(docs=documents)

# 带进度回调
def on_progress(stage, current, total):
    print(f"[{current}/{total}] {stage}")

hipporag.index(docs=documents, progress_callback=on_progress)
```

---

#### `retrieve()`

检索与查询相关的文档。

```python
retrieve(
    queries: List[str],
    num_to_retrieve: int = None,
    gold_docs: List[List[str]] = None
) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `queries` | `List[str]` | 查询列表 |
| `num_to_retrieve` | `int` | 可选，检索文档数量 |
| `gold_docs` | `List[List[str]]` | 可选，用于评估的金标准文档 |

**返回值**：

- `List[QuerySolution]` 或 `(List[QuerySolution], Dict)` - 查询解决方案列表

**示例**：

```python
# 基本检索
results = hipporag.retrieve(
    queries=["苹果公司是什么时候成立的？"],
    num_to_retrieve=5
)

for result in results:
    print(f"Query: {result.query}")
    print(f"Score: {result.score}")
    for doc in result.retrieved_docs:
        print(f"  - {doc.content}")
```

---

#### `rag_qa()`

执行检索增强问答。

```python
rag_qa(
    queries: List[str] = None,
    retrieval_results: List[QuerySolution] = None,
    gold_docs: List[List[str]] = None,
    gold_answers: List[List[str]] = None
) -> List[QuerySolution]
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `queries` | `List[str]` | 查询列表（与 `retrieval_results` 二选一） |
| `retrieval_results` | `List[QuerySolution]` | 预先检索的结果 |
| `gold_docs` | `List[List[str]]` | 可选，用于评估 |
| `gold_answers` | `List[List[str]]` | 可选，用于评估 |

**返回值**：

- `List[QuerySolution]` - 包含答案的查询解决方案列表

**示例**：

```python
# 方式一：直接问答
results = hipporag.rag_qa(queries=["苹果公司的联合创始人是谁？"])
print(results[0].answer)

# 方式二：基于已有检索结果
retrieval_results = hipporag.retrieve(
    queries=["苹果公司的联合创始人是谁？"],
    num_to_retrieve=10
)
qa_results = hipporag.rag_qa(retrieval_results=retrieval_results)
print(qa_results[0].answer)

# 方式三：带评估的问答
results = hipporag.rag_qa(
    queries=["苹果公司的联合创始人是谁？"],
    gold_docs=[["史蒂夫·乔布斯是苹果公司的联合创始人"]],
    gold_answers=[["史蒂夫·乔布斯"]]
)
print(f"Answer: {results[0].answer}")
print(f"QA F1: {results[0].qa_f1}")
```

---

#### `delete()`

从系统中删除文档。

```python
delete(docs_to_delete: List[str]) -> None
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `docs_to_delete` | `List[str]` | 要删除的文档列表 |

**示例**：

```python
# 删除文档
hipporag.delete(docs_to_delete=["要删除的文档内容"])
```

---

#### `initialize_graph()`

初始化或加载图。

```python
initialize_graph() -> ig.Graph
```

**返回值**：

- `ig.Graph` - 初始化的图对象

**示例**：

```python
graph = hipporag.initialize_graph()
print(f"Nodes: {graph.vcount()}, Edges: {graph.ecount()}")
```

---

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `global_config` | `BaseConfig` | 全局配置对象 |
| `working_dir` | `str` | 工作目录路径 |
| `llm_model` | `BaseLLM` | LLM 模型实例 |
| `embedding_model` | `BaseEmbeddingModel` | 嵌入模型实例 |
| `chunk_embedding_store` | `EmbeddingStore` | 文档块嵌入存储 |
| `entity_embedding_store` | `EmbeddingStore` | 实体嵌入存储 |
| `fact_embedding_store` | `EmbeddingStore` | 事实嵌入存储 |
| `graph` | `ig.Graph` | 知识图谱 |
| `ready_to_retrieve` | `bool` | 是否准备好检索 |

---

## BaseConfig 类

全局配置类，控制 HippoRAG 的所有行为参数。

### 构造函数

```python
BaseConfig(
    # LLM 配置
    llm_name: str = 'gpt-4o-mini',
    llm_base_url: str = None,
    embedding_base_url: str = None,
    azure_endpoint: str = None,
    azure_embedding_endpoint: str = None,
    max_new_tokens: int = 2048,
    num_gen_choices: int = 1,
    seed: int = None,
    temperature: float = 0,
    response_format: dict = None,
    max_retry_attempts: int = 5,

    # 存储配置
    force_openie_from_scratch: bool = False,
    force_index_from_scratch: bool = False,
    save_openie: bool = True,

    # 文档处理配置
    text_preprocessor_class_name: str = 'TextPreprocessor',
    preprocess_encoder_name: str = 'gpt-4o',
    preprocess_chunk_overlap_token_size: int = 128,
    preprocess_chunk_max_token_size: int = None,
    preprocess_chunk_func: str = 'by_token',

    # 信息提取配置
    information_extraction_model_name: str = 'openie_openai_gpt',
    openie_mode: str = 'online',
    skip_graph: bool = False,

    # 嵌入配置
    embedding_model_name: str = 'text-embedding-3-small',
    embedding_batch_size: int = 16,
    embedding_return_as_normalized: bool = True,
    embedding_max_seq_len: int = 2048,
    embedding_model_dtype: str = 'auto',

    # pgvector 配置
    use_pgvector: bool = False,
    pgvector_host: str = 'localhost',
    pgvector_port: int = 5432,
    pgvector_database: str = 'hipporag',
    pgvector_user: str = 'postgres',
    pgvector_password: str = '',
    pgvector_index_type: str = 'ivfflat',
    pgvector_index_lists: int = 100,

    # 图配置
    graph_library: str = 'igraph',
    dgraph_config: dict = None,
    synonymy_edge_topk: int = 2047,
    synonymy_edge_query_batch_size: int = 1000,
    synonymy_edge_key_batch_size: int = 10000,
    synonymy_edge_sim_threshold: float = 0.8,
    is_directed_graph: bool = False,

    # 检索配置
    linking_top_k: int = 5,
    retrieval_top_k: int = 200,
    damping: float = 0.5,

    # QA 配置
    max_qa_steps: int = 1,
    qa_top_k: int = 5,

    # 其他配置
    passage_node_weight: float = 0.05,
    rerank_dspy_file_path: str = None,
    save_dir: str = None,
    dataset: str = None,
    graph_type: str = 'facts_and_sim_passage_node_unidirectional',
    corpus_len: int = None
)
```

### 配置参数详解

#### LLM 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm_name` | `str` | `'gpt-4o-mini'` | LLM 模型名称 |
| `llm_base_url` | `str` | `None` | LLM API 端点 URL |
| `azure_endpoint` | `str` | `None` | Azure OpenAI 端点 |
| `azure_embedding_endpoint` | `str` | `None` | Azure 嵌入端点 |
| `max_new_tokens` | `int` | `2048` | 最大生成 token 数 |
| `temperature` | `float` | `0` | 采样温度 |
| `max_retry_attempts` | `int` | `5` | 最大重试次数 |

#### 嵌入配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `embedding_model_name` | `str` | `'text-embedding-3-small'` | 嵌入模型名称 |
| `embedding_base_url` | `str` | `None` | 嵌入 API 端点 URL |
| `embedding_batch_size` | `int` | `16` | 批处理大小 |
| `embedding_max_seq_len` | `int` | `2048` | 最大序列长度 |

#### 检索配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `retrieval_top_k` | `int` | `200` | 每步检索的文档数 |
| `linking_top_k` | `int` | `5` | 每步链接的节点数 |
| `damping` | `float` | `0.5` | PPR 阻尼因子 (0-1) |

#### QA 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_qa_steps` | `int` | `1` | 最大 QA 步数 |
| `qa_top_k` | `int` | `5` | 传入 QA 模型的文档数 |

#### 存储配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_pgvector` | `bool` | `False` | 是否使用 pgvector |
| `pgvector_host` | `str` | `'localhost'` | PostgreSQL 主机 |
| `pgvector_port` | `int` | `5432` | PostgreSQL 端口 |
| `pgvector_database` | `str` | `'hipporag'` | 数据库名称 |
| `pgvector_user` | `str` | `'postgres'` | 用户名 |
| `pgvector_password` | `str` | `''` | 密码 |
| `pgvector_index_type` | `str` | `'ivfflat'` | 索引类型 ('ivfflat' 或 'hnsw') |

#### 图配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `graph_library` | `str` | `'igraph'` | 图库 ('igraph' 或 'dgraph') |
| `dgraph_config` | `dict` | `None` | DGraph 配置 |
| `is_directed_graph` | `bool` | `False` | 是否为有向图 |
| `synonymy_edge_topk` | `int` | `2047` | 同义词边的 k 值 |

---

## 数据类型

### QuerySolution

查询解决方案类，包含查询结果。

```python
@dataclass
class QuerySolution:
    query: str                              # 查询文本
    answer: str                             # 生成的答案
    retrieved_docs: List[Document]          # 检索到的文档列表
    score: float = 0.0                      # 检索分数
    qa_f1: float = 0.0                      # QA F1 分数
    qa_exact_match: float = 0.0             # QA 精确匹配分数
    retrieval_recall: float = 0.0            # 检索召回率
    metadata: Dict = None                   # 元数据
```

### Document

文档类，表示一个检索到的文档。

```python
@dataclass
class Document:
    doc_id: str                             # 文档 ID
    content: str                            # 文档内容
    title: str = ""                         # 文档标题
    metadata: Dict = None                   # 元数据
    embedding: np.ndarray = None           # 嵌入向量
```

### Triple

三元组类，表示知识图谱中的边。

```python
@dataclass
class Triple:
    subject: str                            # 主体
    predicate: str                          # 谓词
    object: str                             # 客体
```

---

## 工具函数

### create_embedding_store()

创建嵌入存储实例的工厂函数。

```python
from hipporag import create_embedding_store

embedding_store = create_embedding_store(
    embedding_model=embedding_model,
    config=config,
    store_type='chunk'  # 'chunk', 'entity', 或 'fact'
)
```

### create_graph_manager()

创建图管理器实例的工厂函数。

```python
from hipporag import create_graph_manager

graph_manager = create_graph_manager(
    global_config=config,
    working_dir='./data',
    graph=graph,
    entity_embedding_store=entity_store,
    chunk_embedding_store=chunk_store,
    fact_embedding_store=fact_store,
    node_to_node_stats={}
)
```

---

## 示例代码

### 完整的 API 使用示例

```python
from hipporag import HippoRAG, BaseConfig

# 1. 配置
config = BaseConfig(
    save_dir='./hipporag_data',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small',
    retrieval_top_k=200,
    qa_top_k=5
)

# 2. 初始化
hipporag = HippoRAG(global_config=config)

# 3. 索引文档
documents = [
    "Python 是一种高级编程语言",
    "Python 由 Guido van Rossum 创建",
    "Django 是 Python 的 Web 框架"
]
hipporag.index(docs=documents)

# 4. 检索
queries = ["Python 是谁创建的？"]
retrieval_results = hipporag.retrieve(queries=queries, num_to_retrieve=5)

# 5. 问答
qa_results = hipporag.rag_qa(queries=queries)
print(f"Answer: {qa_results[0].answer}")
print(f"Retrieved: {[doc.content for doc in qa_results[0].retrieved_docs]}")

# 6. 更新
hipporag.delete(docs_to_delete=["Python 是一种高级编程语言"])
hipporag.index(docs=["Python 是一种通用的高级编程语言"])
```

---

## 更多资源

- [集成指南](./INTEGRATION_GUIDE.md)
- [配置指南](./CONFIGURATION.md)
- [部署指南](./DEPLOYMENT.md)
