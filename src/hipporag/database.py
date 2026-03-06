"""
统一的数据库模块，管理所有 PostgreSQL 表的创建和初始化。

包含以下表：
1. embeddings_chunk - 文档块嵌入向量
2. embeddings_entity - 实体嵌入向量
3. embeddings_fact - 事实嵌入向量
4. books - 书籍元数据
5. book_bindings - 业务与书籍的绑定关系
"""

import logging
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器，负责所有表的初始化和基础操作。
    """

    def __init__(self, db_config: Dict):
        """
        初始化数据库连接并创建所有必要的表。

        Parameters:
            db_config: PostgreSQL 连接配置，包含：
                - host: 主机地址
                - port: 端口
                - database: 数据库名
                - user: 用户名
                - password: 密码
        """
        self.db_config = db_config
        self.conn = None
        self._connect()

    def _connect(self):
        """连接到 PostgreSQL。"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = False
            logger.info("已连接到 PostgreSQL 数据库")
        except Exception as e:
            logger.error(f"连接 PostgreSQL 失败: {e}")
            raise

    def init_all_tables(self, embedding_dim: int = 1024):
        """
        初始化所有表。

        Parameters:
            embedding_dim: 嵌入向量维度，默认 1024
        """
        self._init_pgvector_extension()
        self._init_embedding_tables(embedding_dim)
        self._init_multi_tenancy_tables()
        logger.info("所有表初始化完成")

    def _init_pgvector_extension(self):
        """初始化 pgvector 扩展。"""
        with self.conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.conn.commit()
                logger.info("pgvector 扩展已启用")
            except Exception as e:
                logger.warning(f"无法创建 vector 扩展（可能已存在）: {e}")
                self.conn.rollback()

    # ==================== 嵌入向量表 ====================

    def _init_embedding_tables(self, embedding_dim: int):
        """
        初始化嵌入向量表（chunk, entity, fact）。

        Parameters:
            embedding_dim: 嵌入向量维度
        """
        namespaces = ['chunk', 'entity', 'fact']

        for namespace in namespaces:
            table_name = f"embeddings_{namespace}"
            self._init_embedding_table(table_name, embedding_dim)

    def _init_embedding_table(self, table_name: str, embedding_dim: int):
        """
        初始化单个嵌入向量表。

        Parameters:
            table_name: 表名
            embedding_dim: 嵌入向量维度
        """
        with self.conn.cursor() as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s
            """, (table_name,))
            existing_columns = [row[0] for row in cur.fetchall()]

            # 创建表（如果不存在）
            if not existing_columns:
                cur.execute(f"""
                    CREATE TABLE {table_name} (
                        hash_id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding vector({embedding_dim}),
                        book_id VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                self.conn.commit()
                logger.info(f"已创建表 {table_name}，维度: {embedding_dim}")
            elif 'book_id' not in existing_columns:
                # 添加 book_id 列
                try:
                    cur.execute(f"ALTER TABLE {table_name} ADD COLUMN book_id VARCHAR(64);")
                    self.conn.commit()
                    logger.info(f"已为表 {table_name} 添加 book_id 列")
                except Exception as e:
                    logger.warning(f"无法添加 book_id 列: {e}")
                    self.conn.rollback()

            # 创建 book_id 索引
            try:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_book_id
                    ON {table_name}(book_id);
                """)
                self.conn.commit()
            except Exception as e:
                logger.warning(f"无法创建 book_id 索引: {e}")
                self.conn.rollback()

            # 创建向量索引（IVFFlat 或 HNSW）
            self._create_vector_index(table_name)

    def _create_vector_index(self, table_name: str, index_type: str = "ivfflat", index_lists: int = 100):
        """
        创建向量索引。

        Parameters:
            table_name: 表名
            index_type: 索引类型 ('ivfflat' 或 'hnsw')
            index_lists: IVFFlat 索引的列表数
        """
        index_name = f"{table_name}_embedding_idx"

        with self.conn.cursor() as cur:
            try:
                # 检查索引是否已存在
                cur.execute("""
                    SELECT COUNT(*) FROM pg_indexes WHERE indexname = %s
                """, (index_name,))
                if cur.fetchone()[0] > 0:
                    return

                # 检查表中是否有数据
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]

                if count == 0:
                    logger.debug(f"表 {table_name} 为空，将在首次插入后创建索引")
                    return

                if index_type == "hnsw":
                    cur.execute(f"""
                        CREATE INDEX {index_name}
                        ON {table_name}
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);
                    """)
                else:
                    cur.execute(f"""
                        CREATE INDEX {index_name}
                        ON {table_name}
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = {index_lists});
                    """)

                self.conn.commit()
                logger.info(f"已为表 {table_name} 创建 {index_type} 向量索引")

            except Exception as e:
                logger.warning(f"无法创建向量索引: {e}")
                self.conn.rollback()

    def ensure_vector_index(self, table_name: str, index_type: str = "ivfflat", index_lists: int = 100):
        """
        确保向量索引存在（在数据插入后调用）。

        Parameters:
            table_name: 表名
            index_type: 索引类型
            index_lists: IVFFlat 索引的列表数
        """
        self._create_vector_index(table_name, index_type, index_lists)

    # ==================== 多租户表 ====================

    def _init_multi_tenancy_tables(self):
        """初始化多租户相关的表（books, businesses, book_bindings）。"""
        self._init_books_table()
        self._init_businesses_table()
        self._init_book_bindings_table()

    def _init_books_table(self):
        """初始化 books 表。"""
        with self.conn.cursor() as cur:
            # 创建 books 表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(256),
                    description TEXT,
                    doc_count INT DEFAULT 0,
                    status VARCHAR(16) DEFAULT 'ready',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)

            self.conn.commit()
            logger.info("books 表已初始化")

    def _init_businesses_table(self):
        """初始化 businesses 表。"""
        with self.conn.cursor() as cur:
            # 创建 businesses 表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    business_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(256),
                    description TEXT,
                    status VARCHAR(16) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)

            self.conn.commit()
            logger.info("businesses 表已初始化")

    def _init_book_bindings_table(self):
        """初始化 book_bindings 表。"""
        with self.conn.cursor() as cur:
            # 创建 book_bindings 表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS book_bindings (
                    id SERIAL PRIMARY KEY,
                    business_id VARCHAR(64) NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
                    book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(business_id, book_id)
                );
            """)

            # 创建索引
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_business
                ON book_bindings(business_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_book
                ON book_bindings(book_id);
            """)

            self.conn.commit()
            logger.info("book_bindings 表已初始化")

    # ==================== 表删除操作 ====================

    def drop_embedding_table(self, namespace: str):
        """
        删除指定命名空间的嵌入向量表。

        Parameters:
            namespace: 命名空间（chunk, entity, fact）
        """
        table_name = f"embeddings_{namespace}"
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
            self.conn.commit()
            logger.info(f"已删除表 {table_name}")

    def drop_all_embedding_tables(self):
        """删除所有嵌入向量表。"""
        for namespace in ['chunk', 'entity', 'fact']:
            self.drop_embedding_table(namespace)

    def drop_multi_tenancy_tables(self):
        """删除多租户相关的表。"""
        with self.conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS book_bindings CASCADE;")
            cur.execute("DROP TABLE IF EXISTS books CASCADE;")
            self.conn.commit()
            logger.info("已删除多租户表")

    def drop_all_tables(self):
        """删除所有表。"""
        self.drop_all_embedding_tables()
        self.drop_multi_tenancy_tables()
        logger.info("已删除所有表")

    # ==================== 连接管理 ====================

    def close(self):
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()
            logger.info("已关闭数据库连接")

    def __del__(self):
        """析构时关闭连接。"""
        self.close()

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()


# ==================== 便捷函数 ====================

def init_database(db_config: Dict, embedding_dim: int = 1024) -> DatabaseManager:
    """
    初始化数据库并创建所有必要的表。

    Parameters:
        db_config: PostgreSQL 连接配置
        embedding_dim: 嵌入向量维度

    Returns:
        DatabaseManager 实例
    """
    db = DatabaseManager(db_config)
    db.init_all_tables(embedding_dim)
    return db


def get_db_config_from_env() -> Dict:
    """
    从环境变量获取数据库配置。

    Returns:
        数据库配置字典
    """
    import os

    return {
        'host': os.getenv('PGVECTOR_HOST', 'localhost'),
        'port': int(os.getenv('PGVECTOR_PORT', '5432')),
        'database': os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        'user': os.getenv('PGVECTOR_USER', 'postgres'),
        'password': os.getenv('PGVECTOR_PASSWORD', ''),
    }


# ==================== 静态方法（用于外部连接） ====================

def init_embedding_table_with_conn(conn, table_name: str, embedding_dim: int,
                                    index_type: str = "ivfflat", index_lists: int = 100):
    """
    使用外部连接初始化嵌入向量表。

    Parameters:
        conn: psycopg2 连接对象
        table_name: 表名
        embedding_dim: 嵌入向量维度
        index_type: 索引类型 ('ivfflat' 或 'hnsw')
        index_lists: IVFFlat 索引的列表数
    """
    with conn.cursor() as cur:
        # 启用 pgvector 扩展
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
        except Exception as e:
            logger.warning(f"无法创建 vector 扩展（可能已存在）: {e}")
            conn.rollback()

        # 检查表是否存在
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
        """, (table_name,))
        existing_columns = [row[0] for row in cur.fetchall()]

        # 创建表（如果不存在）
        if not existing_columns:
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    hash_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector({embedding_dim}),
                    book_id VARCHAR(64),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            logger.info(f"已创建表 {table_name}，维度: {embedding_dim}")
        elif 'book_id' not in existing_columns:
            # 添加 book_id 列
            try:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN book_id VARCHAR(64);")
                conn.commit()
                logger.info(f"已为表 {table_name} 添加 book_id 列")
            except Exception as e:
                logger.warning(f"无法添加 book_id 列: {e}")
                conn.rollback()

        # 创建 book_id 索引
        try:
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_book_id
                ON {table_name}(book_id);
            """)
            conn.commit()
        except Exception as e:
            logger.warning(f"无法创建 book_id 索引: {e}")
            conn.rollback()

        # 创建向量索引
        _create_vector_index_with_conn(conn, table_name, index_type, index_lists)


def _create_vector_index_with_conn(conn, table_name: str, index_type: str = "ivfflat", index_lists: int = 100):
    """
    使用外部连接创建向量索引。

    Parameters:
        conn: psycopg2 连接对象
        table_name: 表名
        index_type: 索引类型
        index_lists: IVFFlat 索引的列表数
    """
    index_name = f"{table_name}_embedding_idx"

    with conn.cursor() as cur:
        try:
            # 检查索引是否已存在
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes WHERE indexname = %s
            """, (index_name,))
            if cur.fetchone()[0] > 0:
                return

            # 检查表中是否有数据
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]

            if count == 0:
                logger.debug(f"表 {table_name} 为空，将在首次插入后创建索引")
                return

            if index_type == "hnsw":
                cur.execute(f"""
                    CREATE INDEX {index_name}
                    ON {table_name}
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """)
            else:
                cur.execute(f"""
                    CREATE INDEX {index_name}
                    ON {table_name}
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = {index_lists});
                """)

            conn.commit()
            logger.info(f"已为表 {table_name} 创建 {index_type} 向量索引")

        except Exception as e:
            logger.warning(f"无法创建向量索引: {e}")
            conn.rollback()


def ensure_vector_index_with_conn(conn, table_name: str, index_type: str = "ivfflat", index_lists: int = 100):
    """
    确保向量索引存在（在数据插入后调用）。

    Parameters:
        conn: psycopg2 连接对象
        table_name: 表名
        index_type: 索引类型
        index_lists: IVFFlat 索引的列表数
    """
    _create_vector_index_with_conn(conn, table_name, index_type, index_lists)


def init_multi_tenancy_tables_with_conn(conn):
    """
    使用外部连接初始化多租户表。

    Parameters:
        conn: psycopg2 连接对象
    """
    with conn.cursor() as cur:
        # 创建 books 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                book_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(256),
                description TEXT,
                doc_count INT DEFAULT 0,
                status VARCHAR(16) DEFAULT 'ready',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 创建 businesses 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                business_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(256),
                description TEXT,
                status VARCHAR(16) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 创建 book_bindings 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS book_bindings (
                id SERIAL PRIMARY KEY,
                business_id VARCHAR(64) NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
                book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(business_id, book_id)
            );
        """)

        # 创建索引
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_book_bindings_business
            ON book_bindings(business_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_book_bindings_book
            ON book_bindings(book_id);
        """)

        conn.commit()
        logger.info("多租户表已初始化（books, businesses, book_bindings）")
