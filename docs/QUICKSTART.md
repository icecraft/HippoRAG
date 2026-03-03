# HippoRAG 快速开始指南

本指南帮助您在 5 分钟内开始使用 HippoRAG。

**前置要求**：需运行 DGraph（图存储）和 PostgreSQL + pgvector（向量存储）。

## 1. 安装

```bash
pip install hipporag
```

## 2. 设置环境变量

```bash
export OPENAI_API_KEY=your_openai_api_key
```

## 3. 基础使用

### 索引文档

```python
from hipporag import HippoRAG

# 初始化
hipporag = HippoRAG(
    save_dir='./hipporag_data',
    llm_model_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small'
)

# 索引文档
documents = [
    "苹果公司成立于1976年",
    "史蒂夫·乔布斯是苹果公司的联合创始人",
    "iPhone 是苹果公司的主要产品"
]
hipporag.index(docs=documents)
```

### 查询

```python
# 执行查询
results = hipporag.rag_qa(queries=["苹果公司的联合创始人是谁？"])

# 输出答案
print(results[0].answer)
# 输出: 史蒂夫·乔布斯是苹果公司的联合创始人

# 输出检索到的文档
for doc in results[0].retrieved_docs:
    print(f"- {doc.content}")
```

## 4. 高级用法

### 使用自定义端点

```python
hipporag = HippoRAG(
    save_dir='./data',
    llm_model_name='your-model',
    llm_base_url='https://api.example.com/v1',
    embedding_model_name='your-embedding',
    embedding_base_url='https://api.example.com/v1'
)
```

### 使用 pgvector 和 DGraph（默认配置）

精简版默认使用 pgvector 和 DGraph，需同时配置：

```python
from hipporag import BaseConfig

config = BaseConfig(
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password',
    graph_library='dgraph',
    dgraph_config={'host': 'localhost', 'port': 9080}
)

hipporag = HippoRAG(global_config=config)
```

## 5. API 快速参考

| 方法 | 说明 | 示例 |
|------|------|------|
| `index(docs)` | 索引文档 | `hipporag.index(docs=["内容"])` |
| `retrieve(queries)` | 检索文档 | `hipporag.retrieve(queries=["问题"])` |
| `rag_qa(queries)` | 问答 | `hipporag.rag_qa(queries=["问题"])` |
| `delete(docs)` | 删除文档 | `hipporag.delete(docs=["内容"])` |

## 6. 下一步

- 阅读 [集成指南](./INTEGRATION_GUIDE.md) 了解更多集成方式
- 查看 [API 参考文档](./API_REFERENCE.md) 了解完整 API
- 参考 [配置指南](./CONFIGURATION.md) 进行系统优化

## 常见问题

**Q: 需要什么 API 密钥？**
A: 至少需要 OpenAI API 密钥（或兼容的 LLM API 密钥）。

**Q: 可以使用本地模型吗？**
A: 可以，使用 `transformers_offline` 模式。

**Q: 如何降低成本？**
A: 使用较小的模型（如 `gpt-4o-mini`）和本地嵌入模型。

## 技术支持

如有问题，请访问 [GitHub Issues](https://github.com/OSU-NLP-Group/HippoRAG/issues)。
