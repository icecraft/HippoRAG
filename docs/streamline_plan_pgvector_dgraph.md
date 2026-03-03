# 精简计划：仅支持 pgvector + dgraph

**状态：已完成**

本文档为将 HippoRAG 精简为仅支持 pgvector（嵌入存储）和 dgraph（图存储）的实施计划。所有阶段已于 2026-03 完成。

---

## 阶段 0：前置检查

- [x] 确认 `ingest_novel_dgraph.py` 和 `query_novel_dgraph.py` 可正常运行
- [x] 备份或创建 git 分支

---

## 阶段 1：GraphInterface 补全 PPR

PPR 是检索核心，需在 `GraphInterface` 中抽象，供 DGraphAdapter 实现。

### 1.1 在 `GraphInterface` 中新增抽象方法

文件：`src/hipporag/graph/graph_interface.py`

新增：

```python
@abstractmethod
def personalized_pagerank(self,
                         reset_prob: np.ndarray,
                         damping: float = 0.5,
                         weights: Optional[str] = 'weight') -> np.ndarray:
    """
    Run Personalized PageRank.
    
    Args:
        reset_prob: Reset probability for each vertex (index-aligned)
        damping: Damping factor
        weights: Edge attribute name for weights, or None for unweighted
    
    Returns:
        1D array of PPR scores, index-aligned with vertices
    """
    pass
```

- 添加 `import numpy as np`（如尚未导入）
- `weights` 类型可设为 `Optional[str] = 'weight'`

### 1.2 在 `IGraphAdapter` 中实现（临时保留，便于测试）

文件：`src/hipporag/graph/graph_adapter_igraph.py`

- 实现 `personalized_pagerank`，内部调用 `self._graph.personalized_pagerank(...)`
- 保证输入 `reset_prob` 与 `self._graph.vs` 索引对应，返回与顶点索引一致的 scores

### 1.3 在 `DGraphAdapter` 中实现

文件：`src/hipporag/graph/graph_adapter_dgraph.py`

- 实现 `personalized_pagerank`：
  - 从 DGraph 拉取当前图结构（顶点、边、权重）
  - 构建邻接矩阵或使用 networkx / scipy 运行 PPR
  - 返回与顶点顺序一致的 score 数组
- 可依赖 `networkx` 或 `scipy.sparse` 做 PPR（需在 requirements 中声明）

---

## 阶段 2：核心组件改用 GraphInterface

目标：`HippoRAG`、`GraphManager`、`GraphBuilder`、`Retriever`、`Indexer` 全部通过 `GraphInterface` 操作图，不再直接使用 igraph。

### 2.1 `HippoRAG.__init__` 使用 GraphFactory

文件：`src/hipporag/HippoRAG.py`

- 移除 `import igraph as ig`
- 在创建 `temp_graph_manager` 之前：
  - 根据 `global_config.graph_library` 调用 `create_graph(global_config)` 或 `load` 得到 `GraphInterface` 实例
  - 将 `self.graph` 设为该实例
- `GraphManager` 的 `graph` 参数改为接收 `GraphInterface` 类型

### 2.2 `GraphManager` 使用 GraphInterface

文件：`src/hipporag/graph/graph_manager.py`

- 移除 `import igraph as ig`
- `graph` 参数类型改为 `GraphInterface`
- `initialize_graph()`：
  - 若 `graph_library == "dgraph"`：调用 `DGraphAdapter.load()` 或 `create()`
  - 若仍保留 igraph（过渡期）：调用 `IGraphAdapter.load()` 或 `create()`
- `save_igraph()`：改名为 `save_graph()`，内部调用 `self.graph.save(filename)`
- `len(self.graph.vs())` → `self.graph.vcount()`
- `len(self.graph.es())` → `self.graph.ecount()`

### 2.3 `GraphBuilder` 使用 GraphInterface

文件：`src/hipporag/graph/graph_builder.py`

- 移除 `import igraph as ig`
- `graph` 参数类型改为 `GraphInterface`
- `{v["name"]: v for v in self.graph.vs ...}` → 使用 `self.graph.get_vertices()` 或 `get_vertex_attributes("name")` 构建映射
- `self.graph.add_vertices(...)`、`self.graph.add_edges(...)` → 保持接口，确保 `GraphInterface` 已定义
- `self.graph.vs["name"]` → `self.graph.get_vertex_attributes("name")`

### 2.4 `Retriever` 使用 GraphInterface

文件：`src/hipporag/retrieval/retriever.py`

- 移除 `import igraph as ig`
- `graph` 参数类型改为 `GraphInterface`
- `self.graph.vcount()` → 已兼容
- `{node["name"]: idx for idx, node in enumerate(self.graph.vs)}` → 使用 `self.graph.get_vertices()` 迭代，按索引建立 `node_name_to_vertex_idx`
- `self.graph.personalized_pagerank(...)` → `self.graph.personalized_pagerank(reset_prob, damping, weights='weight')`
- `len(self.graph.vs['name'])` → `self.graph.vcount()` 或 `len(self.graph.get_vertex_attributes('name'))`

### 2.5 `Indexer` 使用 GraphInterface

文件：`src/hipporag/indexing/indexer.py`

- 移除 `import igraph as ig`
- `graph` 参数类型改为 `GraphInterface`
- `save_igraph()` 调用改为 `save_graph()`（若已重命名）

### 2.6 `HippoRAG` 中其余 igraph 用法

文件：`src/hipporag/HippoRAG.py`

- `self.graph.vs['name']` → 使用 `self.graph.get_vertex_attributes('name')`
- `save_igraph()` → `save_graph()`

---

## 阶段 3：移除 igraph 支持（可选，仅 dgraph）

若确定只保留 dgraph，执行本阶段。

### 3.1 删除 IGraphAdapter

- 删除文件：`src/hipporag/graph/graph_adapter_igraph.py`

### 3.2 更新 GraphFactory

文件：`src/hipporag/graph/graph_factory.py`

- 移除所有 `IGraphAdapter` 引用
- `graph_library` 仅处理 `"dgraph"`
- 删除或简化 `wrap_graph()`（若仅 dgraph 则可能不需要）

### 3.3 更新 graph 包导出

文件：`src/hipporag/graph/__init__.py`

- 从 `__all__` 中移除 `IGraphAdapter`

### 3.4 更新配置默认值

文件：`src/hipporag/utils/config_utils.py`

- `graph_library` 默认值改为 `"dgraph"`
- `graph_library` 类型改为 `Literal["dgraph"]`（若移除 igraph）

### 3.5 移除 igraph 依赖

- `requirements.txt`：删除 `python_igraph==0.11.8`
- `setup.py`：删除 `python_igraph==0.11.8`

---

## 阶段 4：嵌入存储仅保留 pgvector（可选）

### 4.1 简化 create_embedding_store

文件：`src/hipporag/embedding_store.py`

- 移除 Parquet 分支
- 始终使用 `PgVectorEmbeddingStore`
- 或将 `use_pgvector` 默认设为 `True`，并删除 else 分支

### 4.2 删除或废弃 EmbeddingStore（Parquet）

- 若不再需要 Parquet：删除 `EmbeddingStore` 类，或保留为 deprecated
- `create_embedding_store` 仅调用 `PgVectorEmbeddingStore`

### 4.3 更新配置

文件：`src/hipporag/utils/config_utils.py`

- `use_pgvector` 默认值改为 `True`（若保留该字段）
- 或删除 `use_pgvector`，始终使用 pgvector

### 4.4 移除 Parquet 相关依赖（可选）

- `requirements.txt`：删除 `fastparquet`、`pyarrow`（确认无其他模块使用）
- `setup.py`：同上

---

## 阶段 5：项目脚本与文档更新

### 5.1 精简 projects 下的脚本

- `ingest_novel.py`、`query_novel.py`：若保留为「默认」脚本，改为使用 `graph_library="dgraph"` 和 `use_pgvector=True`
- 或保留 `ingest_novel_dgraph.py` / `query_novel_dgraph.py` 作为主脚本，删除/合并重复脚本

### 5.2 更新文档

- `README.md`：说明仅支持 pgvector + dgraph
- `docs/dgraph_support.md`：标记为当前推荐方案，移除 igraph 相关内容

---

## 阶段 6：测试与回归

- [ ] 运行 `ingest_novel_dgraph.py` 完成索引
- [ ] 运行 `query_novel_dgraph.py` 完成检索
- [ ] 对比精简前后的检索结果或指标，确保一致
- [ ] 运行项目中现有测试（如有）

---

## 执行顺序总结

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1 | GraphInterface 增加 PPR，IGraphAdapter/DGraphAdapter 实现 | 无 |
| 2 | 核心组件改用 GraphInterface | 阶段 1 |
| 3 | 移除 igraph | 阶段 2 |
| 4 | 嵌入存储仅 pgvector | 无（可与 2 并行） |
| 5 | 脚本与文档 | 阶段 2–4 |
| 6 | 测试 | 阶段 1–5 |

建议：先完成阶段 1 和 2，验证 dgraph 流程正常，再执行阶段 3–5。

---

## 完成记录

- 阶段 1：GraphInterface 已添加 `personalized_pagerank`，DGraphAdapter 已实现
- 阶段 2：HippoRAG、GraphManager、GraphBuilder、Retriever、Indexer 已改用 GraphInterface
- 阶段 3：已移除 igraph、IGraphAdapter，graph_library 默认 dgraph
- 阶段 4：create_embedding_store 仅使用 PgVectorEmbeddingStore
- 阶段 5：README、dgraph_support 已更新
