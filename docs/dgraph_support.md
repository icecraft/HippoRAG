# DGraph 支持说明

本文档说明如何在 HippoRAG 中使用 dgraph 作为 igraph 的替换。

## 概述

HippoRAG 现在支持通过抽象接口使用不同的图库。目前支持：
- **igraph** (默认): 内存中的图库，用于图计算
- **dgraph** (待实现): 分布式图数据库

## 架构设计

### 1. GraphInterface 抽象接口

`GraphInterface` 定义了所有图操作的标准接口，包括：
- 节点和边的添加/访问
- 图属性查询
- 图的保存/加载

### 2. 适配器模式

每个图库通过适配器实现 `GraphInterface`：
- `IGraphAdapter`: igraph 的适配器（已实现）
- `DGraphAdapter`: dgraph 的适配器（待实现）

### 3. 工厂函数

`create_graph()` 函数根据配置自动创建相应的图适配器。

## 使用方法

### 使用 igraph (默认)

```python
from hipporag import BaseConfig, HippoRAG

config = BaseConfig(
    graph_library="igraph",  # 默认值
    # ... 其他配置
)

hipporag = HippoRAG(global_config=config)
```

### 使用 dgraph (待实现)

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

1. **兼容性**: 当前代码仍直接使用 igraph，需要逐步迁移到 GraphInterface
2. **性能**: dgraph 是分布式数据库，适合大规模图，但可能有延迟
3. **功能**: 某些 igraph 特定功能（如 PPR）可能需要特殊处理

## 迁移计划

要完全支持 dgraph，需要：

1. ✅ 创建 GraphInterface 抽象接口
2. ✅ 实现 IGraphAdapter
3. ⏳ 实现 DGraphAdapter（需要 dgraph 客户端库）
4. ⏳ 更新 GraphBuilder 使用 GraphInterface
5. ⏳ 更新 GraphManager 使用 GraphInterface
6. ⏳ 更新 Retriever 使用 GraphInterface
7. ⏳ 更新所有直接访问 `graph.vs` 和 `graph.es` 的代码

## 当前状态

- ✅ 抽象接口已创建
- ✅ igraph 适配器已实现
- ✅ dgraph 适配器已实现（基于 dgraph_examples）
- ✅ 配置选项已添加
- ⏳ 代码迁移待完成（需要将现有代码从直接使用 igraph 迁移到 GraphInterface）

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

