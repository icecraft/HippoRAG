# DGraph 支持说明

本文档说明 HippoRAG 精简版中使用 dgraph 作为图存储。

## 概述

精简版 HippoRAG 仅支持：
- **dgraph**: 分布式图数据库（图存储）
- **pgvector**: PostgreSQL 扩展（向量存储）

## 架构设计

### 1. GraphInterface 抽象接口

`GraphInterface` 定义了所有图操作的标准接口，包括：
- 节点和边的添加/访问
- 图属性查询
- 图的保存/加载

### 2. 适配器模式

DGraph 通过 `DGraphAdapter` 实现 `GraphInterface`。

### 3. 工厂函数

`create_graph()` 函数根据配置自动创建相应的图适配器。

## 使用方法

### 使用 dgraph（默认）

```python
from hipporag import BaseConfig, HippoRAG

config = BaseConfig(
    graph_library="dgraph",
    dgraph_config={
        "host": "localhost",
        "port": 9080,
        # ... 其他 dgraph 配置
    },
    # ... 其他配置
)

hipporag = HippoRAG(global_config=config)
```

## 实现状态

✅ **DGraphAdapter 已实现**

基于 `dgraph_examples` 目录下的示例代码，已实现完整的 DGraphAdapter，包括：

- ✅ `vcount()`: 使用 GraphQL+- 查询节点数量
- ✅ `ecount()`: 查询边数量
- ✅ `add_vertices()`: 使用 mutation 批量添加节点
- ✅ `add_edges()`: 使用 mutation 添加边
- ✅ `get_vertices()`: 查询并缓存所有节点
- ✅ `get_edges()`: 查询并缓存所有边
- ✅ `get_vertex_by_name()`: 根据名称查找节点
- ✅ `get_vertex_attributes()`: 获取节点属性
- ✅ `save()` / `load()`: 图的持久化（导出/导入）
- ✅ Schema 自动初始化
- ✅ `personalized_pagerank()`: 通过 networkx 计算 PPR

## 安装和配置

1. **安装 dgraph Python 客户端**
   ```bash
   pip install pydgraph
   ```

2. **启动 Dgraph 服务**
   
   参考 `dgraph_examples/simple/docker-compose.yml` 启动本地 Dgraph 实例，或连接到远程 Dgraph 服务。

3. **配置连接**
   
   在 `dgraph_config` 中提供连接参数：
   ```python
   dgraph_config = {
       "host": "localhost",
       "port": 9080,
       # 或者使用 grpc 地址：
       # "grpc": "localhost:9080",
       # 或者使用 URL：
       # "url": "dgraph://localhost:9080"
   }
   ```

## 注意事项

1. **前置条件**: 需运行 DGraph 服务（默认 `localhost:9080`）
2. **性能**: DGraph 为分布式数据库，适合大规模图，单次操作可能有网络延迟
3. **PPR**: DGraphAdapter 通过导出到 networkx 实现 personalized_pagerank
4. **删除节点**: `delete_vertices` 在 DGraphAdapter 中尚未实现，Indexer 的 delete 功能在使用 dgraph 时受限

## 实现细节

### Schema 定义

DGraphAdapter 自动创建以下 schema：
- `name: string @index(exact)` - 节点名称（带索引）
- `node_type: string @index(exact)` - 节点类型
- `content: string` - 节点内容
- `properties: string` - 节点属性（JSON 字符串）
- `weight: float` - 边权重
- `edge_type: string` - 边类型
- `Relation: [uid]` - 边关系

### 缓存机制

为了提高性能，DGraphAdapter 实现了缓存：
- 节点缓存：`_vertex_cache` 和 `_name_to_uid` 映射
- 边缓存：`_edge_cache`
- 缓存会在数据变更时自动清除，需要时重新加载

### 兼容性包装

提供了 `DGraphVertex` 和 `DGraphEdge` 包装类，提供与 igraph 类似的接口：
- `vertex["name"]` 或 `vertex.get("name")`
- `edge.source` 和 `edge.target`（返回索引）
- `edge["weight"]` 或 `edge.get("weight")`

