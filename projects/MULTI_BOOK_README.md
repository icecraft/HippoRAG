# MultiBookHippoRAG 使用指南

`MultiBookHippoRAG` 是一个用于管理多本书籍的 HippoRAG 管理器类，允许您：
- 为每本书创建独立的索引
- 查询单本书或多本书
- 管理书籍元数据
- 跨书籍搜索

## 快速开始

### 基本使用

```python
from hipporag import MultiBookHippoRAG
from hipporag.utils.config_utils import BaseConfig

# 1. 创建基础配置
config = BaseConfig(
    save_dir='outputs/multi_books',
    llm_name='gpt-4o-mini',
    embedding_model_name='text-embedding-3-small',
    llm_base_url='https://api.openai.com/v1',
)

# 2. 创建管理器
manager = MultiBookHippoRAG(base_config=config)

# 3. 添加书籍
book1_chapters = ["第一章内容...", "第二章内容..."]
manager.add_book(
    book_id="book1",
    chapters=book1_chapters,
    metadata={'title': '书籍1', 'author': '作者1'}
)

book2_chapters = ["第一章内容...", "第二章内容..."]
manager.add_book(
    book_id="book2",
    chapters=book2_chapters,
    metadata={'title': '书籍2', 'author': '作者2'}
)

# 4. 查询单本书
results = manager.query_single_book("book1", "某个问题")

# 5. 查询多本书
results = manager.query("某个问题", book_ids=["book1", "book2"])
```

## API 参考

### MultiBookHippoRAG

#### `__init__(base_config, base_save_dir=None)`

初始化多书籍管理器。

**参数：**
- `base_config` (BaseConfig): 基础配置，所有书籍共享
- `base_save_dir` (str, optional): 基础保存目录，每本书保存在子目录中

#### `add_book(book_id, chapters, force_index_from_scratch=False, force_openie_from_scratch=False, metadata=None)`

添加并索引一本书。

**参数：**
- `book_id` (str): 书籍唯一标识符
- `chapters` (List[str]): 章节/文档列表
- `force_index_from_scratch` (bool): 是否从头重建索引
- `force_openie_from_scratch` (bool): 是否从头重建 OpenIE
- `metadata` (Dict, optional): 书籍元数据

**返回：** HippoRAG 实例

#### `query_single_book(book_id, query, **kwargs)`

查询单本书。

**参数：**
- `book_id` (str): 书籍标识符
- `query` (str): 查询字符串
- `**kwargs`: 传递给 `rag_qa()` 的额外参数

**返回：** `(solutions, messages, metadata)` 元组

#### `query(query, book_ids=None, merge_results=True, **kwargs)`

查询一本或多本书。

**参数：**
- `query` (str): 查询字符串
- `book_ids` (List[str], optional): 要查询的书籍列表，None 表示查询所有书籍
- `merge_results` (bool): 是否合并结果（True）或按书籍分组（False）
- `**kwargs`: 传递给 `rag_qa()` 的额外参数

**返回：**
- 如果 `merge_results=True`: 合并的结果列表，每个结果包含 `metadata['book_id']`
- 如果 `merge_results=False`: 字典，键为 `book_id`，值为 `(solutions, messages, metadata)`

#### `list_books()`

列出所有书籍及其元数据。

**返回：** 书籍信息列表

#### `get_book_info(book_id)`

获取特定书籍的详细信息。

**参数：**
- `book_id` (str): 书籍标识符

**返回：** 书籍信息字典

#### `remove_book(book_id, delete_files=False)`

删除书籍。

**参数：**
- `book_id` (str): 书籍标识符
- `delete_files` (bool): 是否同时删除磁盘上的文件

#### `load_existing_book(book_id)`

加载之前索引的书籍（不重新索引）。

**参数：**
- `book_id` (str): 书籍标识符

**返回：** HippoRAG 实例

## 使用场景

### 场景 1: 管理多本小说

```python
manager = MultiBookHippoRAG(base_config=config)

# 索引多本小说
manager.add_book("novel1", novel1_chapters, metadata={'title': '小说1'})
manager.add_book("novel2", novel2_chapters, metadata={'title': '小说2'})
manager.add_book("novel3", novel3_chapters, metadata={'title': '小说3'})

# 查询特定小说
result = manager.query_single_book("novel1", "主角是谁？")

# 跨小说查询
results = manager.query("有哪些角色？", book_ids=["novel1", "novel2"])
```

### 场景 2: 使用 pgvector 和 Nebula Graph

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

### 场景 3: 从文件加载书籍

```python
import json

def load_book_from_file(filepath: str) -> List[str]:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

manager = MultiBookHippoRAG(base_config=config)

# 从文件加载并索引
book1_chapters = load_book_from_file('data/book1.json')
manager.add_book("book1", book1_chapters)

book2_chapters = load_book_from_file('data/book2.json')
manager.add_book("book2", book2_chapters)
```

### 场景 4: 更新书籍

```python
# 更新书籍内容
new_chapters = ["新章节1...", "新章节2..."]
manager.update_book("book1", new_chapters, force_index_from_scratch=True)
```

## 目录结构

使用 `MultiBookHippoRAG` 后，目录结构如下：

```
outputs/multi_books/
├── book1/
│   ├── vdb_chunk.parquet
│   ├── vdb_entity.parquet
│   ├── vdb_fact.parquet
│   └── graph.pkl
├── book2/
│   ├── vdb_chunk.parquet
│   ├── vdb_entity.parquet
│   ├── vdb_fact.parquet
│   └── graph.pkl
└── ...
```

每本书都有独立的索引目录，互不干扰。

## 注意事项

1. **书籍隔离**: 每本书使用独立的索引，查询时不会混淆
2. **元数据**: 可以为每本书添加自定义元数据（标题、作者等）
3. **性能**: 查询多本书时，会依次查询每本书，然后合并结果
4. **存储**: 每本书的索引保存在独立的子目录中
5. **配置共享**: 所有书籍共享基础配置（LLM、embedding 模型等）

## 完整示例

参见 `projects/multi_book_example.py` 获取完整的使用示例。

