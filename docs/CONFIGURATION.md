# HippoRAG 配置指南

本文档详细介绍了 HippoRAG 的配置选项，帮助您根据实际需求优化系统性能。

## 目录

- [配置概述](#配置概述)
- [LLM 配置](#llm-配置)
- [嵌入配置](#嵌入配置)
- [存储配置](#存储配置)
- [图配置](#图配置)
- [检索配置](#检索配置)
- [QA 配置](#qa-配置)
- [文档处理配置](#文档处理配置)
- [性能优化配置](#性能优化配置)
- [配置示例](#配置示例)

---

## 配置概述

HippoRAG 使用 `BaseConfig` 类统一管理所有配置参数。配置可以通过构造函数直接传递，或通过环境变量设置。

### 配置方式

#### 方式一：通过 BaseConfig

```python
from hipporag import HippoRAG, BaseConfig

config = BaseConfig(
    save_dir='./data',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)

hipporag = HippoRAG(global_config=config)
```

#### 方式二：通过 HippoRAG 构造函数

```python
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)
```

#### 方式三：通过环境变量

```bash
export HIPPORAG_LLM_NAME='gpt-4o-mini'
export HIPPORAG_EMBEDDING_MODEL_NAME='text-embedding-3-small'
export HIPPORAG_SAVE_DIR='./data'
```

---

## LLM 配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm_name` | `str` | `'gpt-4o-mini'` | LLM 模型名称 |
| `llm_base_url` | `str` | `None` | LLM API 端点 URL |
| `azure_endpoint` | `str` | `None` | Azure OpenAI 端点 |
| `azure_embedding_endpoint` | `str` | `None` | Azure 嵌入端点 |
| `max_new_tokens` | `int` | `2048` | 最大生成 token 数 |
| `num_gen_choices` | `int` | `1` | 生成的候选数量 |
| `seed` | `int` | `None` | 随机种子 |
| `temperature` | `float` | `0` | 采样温度 (0-1) |
| `max_retry_attempts` | `int` | `5` | 最大重试次数 |

### OpenAI 配置

```python
config = BaseConfig(
    llm_name='gpt-4o-mini',
    llm_base_url='https://api.openai.com/v1',
    max_new_tokens=2048,
    temperature=0,
    max_retry_attempts=5
)
```

### Azure OpenAI 配置

```python
config = BaseConfig(
    llm_name='gpt-4o-mini',
    azure_endpoint='https://your-resource.openai.azure.com/',
    azure_embedding_endpoint='https://your-resource.openai.azure.com/',
    max_new_tokens=2048,
    temperature=0
)
```

### 自定义端点配置

```python
config = BaseConfig(
    llm_name='custom-model',
    llm_base_url='https://api.example.com/v1',
    max_new_tokens=4096,
    temperature=0.7,
    max_retry_attempts=10
)
```

### 本地模型配置

```python
config = BaseConfig(
    llm_name='transformers_offline',  # 使用离线 transformers 模式
    llm_base_url='meta-llama/Llama-2-7b-chat-hf',
    max_new_tokens=512,
    temperature=0
)
```

---

## 嵌入配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `embedding_model_name` | `str` | `'text-embedding-3-small'` | 嵌入模型名称 |
| `embedding_base_url` | `str` | `None` | 嵌入 API 端点 URL |
| `embedding_batch_size` | `int` | `16` | 批处理大小 |
| `embedding_max_seq_len` | `int` | `2048` | 最大序列长度 |
| `embedding_return_as_normalized` | `bool` | `True` | 是否归一化嵌入 |
| `embedding_model_dtype` | `str` | `'auto'` | 模型数据类型 |

### OpenAI 嵌入配置

```python
config = BaseConfig(
    embedding_model_name='text-embedding-3-small',
    embedding_base_url='https://api.openai.com/v1',
    embedding_batch_size=16,
    embedding_max_seq_len=8191  # OpenAI 的最大长度
)
```

### NVIDIA NV-Embed 配置

```python
config = BaseConfig(
    embedding_model_name='nvidia/NV-Embed-v2',
    embedding_batch_size=32,
    embedding_max_seq_len=2048
)
```

### 高性能嵌入配置

```python
config = BaseConfig(
    embedding_model_name='text-embedding-3-small',
    embedding_batch_size=128,  # 增大批处理
    embedding_max_seq_len=2048,
    embedding_model_dtype='float16'  # 使用半精度加速
)
```

---

## 存储配置

### pgvector 配置（必须）

精简版仅支持 pgvector 作为嵌入存储，需配置 PostgreSQL 与 pgvector 扩展。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_pgvector` | `bool` | `True` | 是否使用 pgvector（精简版始终为 True） |
| `pgvector_host` | `str` | `'localhost'` | PostgreSQL 主机 |
| `pgvector_port` | `int` | `5432` | PostgreSQL 端口 |
| `pgvector_database` | `str` | `'hipporag'` | 数据库名称 |
| `pgvector_user` | `str` | `'postgres'` | 用户名 |
| `pgvector_password` | `str` | `''` | 密码 |
| `pgvector_index_type` | `str` | `'ivfflat'` | 索引类型 ('ivfflat' 或 'hnsw') |
| `pgvector_index_lists` | `int` | `100` | IVFFlat 索引列表数 |

### pgvector 配置示例

```python
# 基本配置
config = BaseConfig(
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password'
)

# 使用 HNSW 索引（更快）
config = BaseConfig(
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password',
    pgvector_index_type='hnsw'
)

# 使用 IVFFlat 索引（更省内存）
config = BaseConfig(
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password',
    pgvector_index_type='ivfflat',
    pgvector_index_lists=100  # 根据数据量调整
)
```

### 存储重置配置

```python
config = BaseConfig(
    force_openie_from_scratch=True,  # 重建 OpenIE 结果
    force_index_from_scratch=True    # 重建所有索引
)
```

---

## 图配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `graph_library` | `str` | `'dgraph'` | 图库（精简版仅支持 dgraph） |
| `dgraph_config` | `dict` | `None` | DGraph 配置 |
| `is_directed_graph` | `bool` | `False` | 是否为有向图 |
| `synonymy_edge_topk` | `int` | `2047` | 同义词边的 k 值 |
| `synonymy_edge_query_batch_size` | `int` | `1000` | 查询批处理大小 |
| `synonymy_edge_key_batch_size` | `int` | `10000` | 键批处理大小 |
| `synonymy_edge_sim_threshold` | `float` | `0.8` | 相似度阈值 |
| `passage_node_weight` | `float` | `0.05` | 文档节点权重 |

### DGraph 配置

```python
config = BaseConfig(
    graph_library='dgraph',
    dgraph_config={
        'host': 'localhost',
        'port': 9080,          # Alpha port
        'alpha_port': 9080,
        'zero_port': 5080
    },
    is_directed_graph=True
)
```

### 图类型配置

```python
# 不同的图构建策略
config = BaseConfig(
    graph_type='facts_and_sim_passage_node_unidirectional'  # 默认
)

# 可选的图类型:
# - 'dpr_only': 仅 DPR
# - 'entity': 仅实体
# - 'passage_entity': 文档 + 实体
# - 'relation_aware_passage_entity': 关系感知文档实体
# - 'passage_entity_relation': 文档实体关系
# - 'facts_and_sim_passage_node_unidirectional': 事实 + 相似文档节点（单向）
```

---

## 检索配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `retrieval_top_k` | `int` | `200` | 每步检索的文档数 |
| `linking_top_k` | `int` | `5` | 每步链接的节点数 |
| `damping` | `float` | `0.5` | PPR 阻尼因子 (0-1) |
| `passage_node_weight` | `float` | `0.05` | 文档节点在 PPR 中的权重 |

### 基本检索配置

```python
config = BaseConfig(
    retrieval_top_k=200,  # 初始检索文档数
    linking_top_k=5,      # 每步链接节点数
    damping=0.5           # PPR 阻尼因子
)
```

### 高召回率检索配置

```python
config = BaseConfig(
    retrieval_top_k=500,  # 增加检索文档数
    linking_top_k=10,      # 增加链接节点数
    damping=0.3           # 降低阻尼因子，增加随机游走
)
```

### 高精度检索配置

```python
config = BaseConfig(
    retrieval_top_k=100,  # 减少检索文档数
    linking_top_k=3,      # 减少链接节点数
    damping=0.7,          # 提高阻尼因子，更依赖初始节点
    passage_node_weight=0.1  # 增加文档节点权重
)
```

---

## QA 配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_qa_steps` | `int` | `1` | 最大 QA 步数 |
| `qa_top_k` | `int` | `5` | 传入 QA 模型的文档数 |

### 基本 QA 配置

```python
config = BaseConfig(
    max_qa_steps=1,
    qa_top_k=5
)
```

### 多步推理配置

```python
config = BaseConfig(
    max_qa_steps=3,   # 允许最多 3 步推理
    qa_top_k=10       # 每步使用更多文档
)
```

### 快速 QA 配置

```python
config = BaseConfig(
    max_qa_steps=1,
    qa_top_k=3         # 使用更少文档
)
```

---

## 文档处理配置

### 基本配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text_preprocessor_class_name` | `str` | `'TextPreprocessor'` | 预处理器类名 |
| `preprocess_encoder_name` | `str` | `'gpt-4o'` | 预处理编码器 |
| `preprocess_chunk_overlap_token_size` | `int` | `128` | 块重叠 token 数 |
| `preprocess_chunk_max_token_size` | `int` | `None` | 块最大 token 数 |
| `preprocess_chunk_func` | `str` | `'by_token'` | 分块方式 |

### 文档分块配置

```python
# 按 token 分块
config = BaseConfig(
    preprocess_chunk_max_token_size=512,   # 每块最大 token 数
    preprocess_chunk_overlap_token_size=64,  # 重叠 token 数
    preprocess_chunk_func='by_token'
)

# 按词分块
config = BaseConfig(
    preprocess_chunk_max_token_size=512,
    preprocess_chunk_overlap_token_size=64,
    preprocess_chunk_func='by_word'
)

# 不分块（整文档）
config = BaseConfig(
    preprocess_chunk_max_token_size=None  # None 表示不分块
)
```

### 信息提取配置

```python
config = BaseConfig(
    information_extraction_model_name='openie_openai_gpt',
    openie_mode='online',  # 目前仅支持 'online'
    skip_graph=False       # 是否跳过图构建
)

# 跳过图构建（仅使用 DPR 检索）
config = BaseConfig(
    skip_graph=True
)
```

---

## 性能优化配置

### 速度优化

```python
# 更快的嵌入处理
config = BaseConfig(
    embedding_batch_size=64,        # 增大批处理
    embedding_model_dtype='float16',  # 使用半精度
    embedding_max_seq_len=512        # 减少序列长度
)

# 更快的检索
config = BaseConfig(
    retrieval_top_k=100,            # 减少检索文档数
    linking_top_k=3,                 # 减少链接节点数
    max_qa_steps=1                   # 单步推理
)

# 使用 pgvector HNSW 索引
config = BaseConfig(
    use_pgvector=True,
    pgvector_index_type='hnsw'
)
```

### 精度优化

```python
# 更高精度的嵌入
config = BaseConfig(
    embedding_model_name='text-embedding-3-large',  # 使用大模型
    embedding_batch_size=8,                          # 更小批次
    embedding_max_seq_len=8191
)

# 更高精度的检索
config = BaseConfig(
    retrieval_top_k=500,      # 更多候选文档
    linking_top_k=10,          # 更多链接节点
    max_qa_steps=3,           # 多步推理
    damping=0.3                # 更宽松的随机游走
)

# 更高质量的开源信息提取
config = BaseConfig(
    preprocess_encoder_name='gpt-4o',  # 使用更强大的模型
    temperature=0                        # 确定性输出
)
```

### 内存优化

```python
# 使用 pgvector 减少内存占用
config = BaseConfig(
    use_pgvector=True,
    pgvector_index_type='ivfflat'  # IVFFlat 比 HNSW 更省内存
)

# 减少序列长度
config = BaseConfig(
    embedding_max_seq_len=512,
    preprocess_chunk_max_token_size=512
)

# 使用半精度
config = BaseConfig(
    embedding_model_dtype='float16'
)
```

---

## 配置示例

### 开发环境配置

```python
config = BaseConfig(
    # 存储（精简版需 pgvector）
    save_dir='./dev_data',
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='',

    # LLM
    llm_name='gpt-4o-mini',
    max_new_tokens=1024,
    temperature=0,

    # 嵌入
    embedding_model_name='text-embedding-3-small',
    embedding_batch_size=16,

    # 检索
    retrieval_top_k=100,
    linking_top_k=5,

    # QA
    max_qa_steps=1,
    qa_top_k=5
)
```

### 生产环境配置

```python
config = BaseConfig(
    # 存储
    save_dir='/data/hipporag',
    use_pgvector=True,
    pgvector_host='db.example.com',
    pgvector_port=5432,
    pgvector_database='hipporag_prod',
    pgvector_user='hipporag_user',
    pgvector_password='secure_password',
    pgvector_index_type='hnsw',

    # LLM
    llm_name='gpt-4o-mini',
    llm_base_url='https://api.openai.com/v1',
    max_new_tokens=2048,
    temperature=0,
    max_retry_attempts=10,

    # 嵌入
    embedding_model_name='text-embedding-3-small',
    embedding_base_url='https://api.openai.com/v1',
    embedding_batch_size=32,

    # 检索
    retrieval_top_k=200,
    linking_top_k=5,
    damping=0.5,

    # QA
    max_qa_steps=2,
    qa_top_k=10
)
```

### 大规模数据集配置

```python
config = BaseConfig(
    # 存储 - 使用数据库
    save_dir='/data/hipporag_large',
    use_pgvector=True,
    pgvector_index_type='hnsw',

    # 图 - 使用 DGraph
    graph_library='dgraph',
    dgraph_config={
        'host': 'dgraph.example.com',
        'port': 9080
    },

    # 嵌入 - 大批处理
    embedding_model_name='text-embedding-3-small',
    embedding_batch_size=128,
    embedding_model_dtype='float16',

    # 检索
    retrieval_top_k=300,
    linking_top_k=10,
    damping=0.4,

    # QA
    max_qa_steps=3,
    qa_top_k=15
)
```

### 低延迟配置

```python
config = BaseConfig(
    # 使用 pgvector HNSW
    use_pgvector=True,
    pgvector_index_type='hnsw',

    # 较小的检索范围
    retrieval_top_k=50,
    linking_top_k=3,

    # 单步推理
    max_qa_steps=1,
    qa_top_k=3,

    # 较短的生成
    max_new_tokens=512
)
```

### 高精度配置

```python
config = BaseConfig(
    # 大嵌入模型
    embedding_model_name='text-embedding-3-large',

    # 大检索范围
    retrieval_top_k=500,
    linking_top_k=15,

    # 多步推理
    max_qa_steps=3,
    qa_top_k=15,

    # 高质量预处理
    preprocess_encoder_name='gpt-4o',
    preprocess_chunk_max_token_size=256,
    preprocess_chunk_overlap_token_size=32
)
```

---

## 更多资源

- [集成指南](./INTEGRATION_GUIDE.md)
- [API 参考文档](./API_REFERENCE.md)
- [部署指南](./DEPLOYMENT.md)
