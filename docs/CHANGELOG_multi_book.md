# MultiBookHippoRAG 变更日志

## 2024-02-03: 新增 MultiBookHippoRAG 功能

### 新增功能

- **MultiBookHippoRAG 类**：多书籍管理器，支持管理多本书籍的独立索引和查询

### 新增文件

1. `src/hipporag/multi_book_manager.py`
   - 实现 `MultiBookHippoRAG` 类
   - 提供书籍添加、查询、管理等功能

2. `projects/multi_book_example.py`
   - 完整的使用示例代码

3. `projects/MULTI_BOOK_README.md`
   - 详细的使用文档和 API 参考

4. `docs/multi_book_manager.md`
   - 实现总结文档

### 修改文件

1. `src/hipporag/__init__.py`
   - 添加 `MultiBookHippoRAG` 的导出

### 主要特性

- ✅ 书籍隔离：每本书使用独立的索引目录
- ✅ 单本书查询：支持查询特定书籍
- ✅ 多本书查询：支持跨书籍搜索
- ✅ 元数据管理：支持为每本书添加元数据
- ✅ 完全兼容：支持 pgvector 和 Nebula Graph
- ✅ 向后兼容：不影响现有 HippoRAG 使用方式

### 使用方式

```python
from hipporag import MultiBookHippoRAG
from hipporag.utils.config_utils import BaseConfig

config = BaseConfig(save_dir='outputs/multi_books', ...)
manager = MultiBookHippoRAG(base_config=config)

# 添加书籍
manager.add_book("book1", chapters1, metadata={'title': '书籍1'})

# 查询
results = manager.query_single_book("book1", "某个问题")
results = manager.query("某个问题", book_ids=["book1", "book2"])
```

### 解决的问题

- ✅ 解决了多本书索引后无法区分来源的问题
- ✅ 提供了清晰的书籍管理机制
- ✅ 支持灵活的查询方式

