# MultiBookHippoRAG 实现总结

## 概述

本次修改实现了 `MultiBookHippoRAG` 类，用于管理多本书籍的索引和查询。该功能解决了在 ingest 多本书后如何区分和查询不同书籍的问题。

## 问题背景

在原始实现中，如果使用 `HippoRAG.index()` 方法索引多本书，所有书籍的内容会混在一起存储在同一个索引中，查询时无法区分结果来自哪本书。这导致：

1. **无法区分来源**：查询结果无法知道来自哪本书
2. **无法按书籍过滤**：无法只查询特定书籍
3. **管理困难**：多本书混在一起难以管理

## 解决方案

实现了 `MultiBookHippoRAG` 类，采用**书籍隔离**的策略：

- 每本书使用独立的 `HippoRAG` 实例
- 每本书的索引保存在独立的子目录中
- 支持单本书查询和跨书籍查询
- 支持书籍元数据管理

## 实现细节

### 1. 核心类：MultiBookHippoRAG

**文件位置**：`src/hipporag/multi_book_manager.py`

**主要功能**：
- 管理多个独立的 `HippoRAG` 实例
- 为每本书创建独立的索引目录
- 提供统一的查询接口
- 支持书籍元数据管理

### 2. 目录结构

使用 `MultiBookHippoRAG` 后，索引目录结构如下：

```
outputs/multi_books/
├── book1/                    # 书籍1的独立索引
│   ├── vdb_chunk.parquet
│   ├── vdb_entity.parquet
│   ├── vdb_fact.parquet
│   └── graph.pkl
├── book2/                    # 书籍2的独立索引
│   ├── vdb_chunk.parquet
│   ├── vdb_entity.parquet
│   ├── vdb_fact.parquet
│   └── graph.pkl
└── ...
```

### 3. 主要方法

#### 初始化
```python
manager = MultiBookHippoRAG(base_config=config)
```

#### 添加书籍
```python
manager.add_book(
    book_id="book1",
    chapters=["Chapter 1...", "Chapter 2..."],
    metadata={'title': '书籍1', 'author': '作者1'}
)
```

#### 查询单本书
```python
solutions, messages, metadata = manager.query_single_book("book1", "某个问题")
```

#### 查询多本书
```python
# 合并结果
results = manager.query("某个问题", book_ids=["book1", "book2"], merge_results=True)

# 按书籍分组
book_results = manager.query("某个问题", book_ids=["book1", "book2"], merge_results=False)
```

#### 其他方法
- `list_books()`: 列出所有书籍
- `get_book_info(book_id)`: 获取书籍信息
- `remove_book(book_id, delete_files=False)`: 删除书籍
- `update_book(book_id, chapters, ...)`: 更新书籍
- `load_existing_book(book_id)`: 加载已存在的书籍

### 4. 模块导出

**文件位置**：`src/hipporag/__init__.py`

已更新，导出 `MultiBookHippoRAG` 类：

```python
from .HippoRAG import HippoRAG
from .multi_book_manager import MultiBookHippoRAG

__all__ = ['HippoRAG', 'MultiBookHippoRAG']
```

## 使用示例

### 基本使用

```python
from hipporag import MultiBookHippoRAG
from hipporag.utils.config_utils import BaseConfig

# 创建配置
config = BaseConfig(
    save_dir='outputs/multi_books',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small',
    llm_base_url='https://api.openai.com/v1',
)

# 创建管理器
manager = MultiBookHippoRAG(base_config=config)

# 添加书籍
manager.add_book("book1", chapters1, metadata={'title': '书籍1'})
manager.add_book("book2", chapters2, metadata={'title': '书籍2'})

# 查询单本书
results = manager.query_single_book("book1", "某个问题")

# 查询多本书
results = manager.query("某个问题", book_ids=["book1", "book2"])
```

### 与 pgvector 和 Nebula Graph 集成

`MultiBookHippoRAG` 完全兼容 pgvector 和 Nebula Graph：

```python
config = BaseConfig(
    save_dir='outputs/multi_books',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small',
    
    # 启用 pgvector
    use_pgvector=True,
    pgvector_host='localhost',
    pgvector_port=5432,
    pgvector_database='hipporag',
    pgvector_user='postgres',
    pgvector_password='your_password',
    
    # 启用 Nebula Graph
    use_nebula_graph=True,
    nebula_host='127.0.0.1',
    nebula_port=9669,
    nebula_user='root',
    nebula_password='nebula',
    nebula_space_name='hipporag',
)

manager = MultiBookHippoRAG(base_config=config)
# 每本书会自动使用独立的数据库表/Space
manager.add_book("book1", chapters1)
manager.add_book("book2", chapters2)
```

## 技术特点

### 1. 书籍隔离

- 每本书使用独立的 `HippoRAG` 实例
- 索引文件完全隔离，互不干扰
- 可以独立管理每本书

### 2. 元数据支持

- 支持为每本书添加自定义元数据
- 元数据存储在内存中，便于查询和管理
- 可以存储标题、作者、描述等信息

### 3. 灵活查询

- **单本书查询**：精确查询特定书籍
- **多本书查询**：支持跨书籍搜索
- **结果合并**：自动合并多本书的查询结果并按相关性排序
- **结果分组**：可以选择按书籍分组返回结果

### 4. 配置共享

- 所有书籍共享基础配置（LLM、embedding 模型等）
- 每本书可以有自己的保存目录
- 支持全局配置和书籍级配置

### 5. 向后兼容

- 不影响现有的 `HippoRAG` 使用方式
- 可以逐步迁移到多书籍管理
- 支持加载已存在的书籍索引

## 文件清单

### 新增文件

1. **`src/hipporag/multi_book_manager.py`**
   - `MultiBookHippoRAG` 类的完整实现
   - 包含所有管理方法

2. **`projects/multi_book_example.py`**
   - 完整的使用示例
   - 演示各种使用场景

3. **`projects/MULTI_BOOK_README.md`**
   - 详细的使用文档
   - API 参考和使用指南

### 修改文件

1. **`src/hipporag/__init__.py`**
   - 添加 `MultiBookHippoRAG` 的导出

## 优势

1. **清晰的书籍管理**：每本书独立索引，易于管理
2. **灵活的查询方式**：支持单本书和多本书查询
3. **元数据支持**：可以为每本书添加丰富的元数据
4. **完全兼容**：与 pgvector 和 Nebula Graph 完全兼容
5. **易于使用**：API 设计简洁直观

## 使用场景

1. **多本小说管理**：管理多本小说的索引和查询
2. **文档集合**：管理多个文档集合
3. **知识库管理**：为不同主题的知识库创建独立索引
4. **版本管理**：为同一本书的不同版本创建独立索引

## 注意事项

1. **存储空间**：每本书需要独立的存储空间
2. **查询性能**：查询多本书时，会依次查询每本书，然后合并结果
3. **配置一致性**：所有书籍共享基础配置，确保一致性
4. **书籍标识**：`book_id` 必须唯一，建议使用有意义的标识符

## 未来改进方向

1. **批量操作**：支持批量添加、删除书籍
2. **索引优化**：优化多本书查询的性能
3. **元数据持久化**：将元数据持久化到文件
4. **书籍搜索**：支持按元数据搜索书籍
5. **索引统计**：提供更详细的索引统计信息

## 总结

`MultiBookHippoRAG` 的实现解决了多本书籍管理的问题，提供了清晰的书籍隔离机制和灵活的查询方式。该实现完全兼容现有的 HippoRAG 功能，包括 pgvector 和 Nebula Graph 支持，可以无缝集成到现有工作流中。

