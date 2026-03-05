#!/usr/bin/env python3
"""
测试新增的 business 管理功能。
"""
import sys
import os

# 直接导入需要的模块，避免触发完整的 HippoRAG 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

# 直接导入 database 模块
from hipporag.database import init_multi_tenancy_tables_with_conn
import psycopg2


def get_db_config():
    """Get database configuration from environment."""
    return {
        'host': os.getenv('PGVECTOR_HOST', 'localhost'),
        'port': int(os.getenv('PGVECTOR_PORT', '5432')),
        'database': os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        'user': os.getenv('PGVECTOR_USER', 'postgres'),
        'password': os.getenv('PGVECTOR_PASSWORD', ''),
    }


def test_businesses_table():
    """测试 businesses 表是否正确创建。"""
    print("\n=== Test: Businesses Table ===")

    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False

    # 初始化表
    init_multi_tenancy_tables_with_conn(conn)
    print("✓ 表初始化完成")

    # 检查 businesses 表是否存在
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name IN ('books', 'businesses', 'book_bindings')
        """)
        tables = [row[0] for row in cur.fetchall()]
        assert 'books' in tables, "books 表不存在"
        assert 'businesses' in tables, "businesses 表不存在"
        assert 'book_bindings' in tables, "book_bindings 表不存在"

    print("✓ 所有表存在 (books, businesses, book_bindings)")

    # 检查 businesses 表结构
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'businesses'
        """)
        columns = {row[0]: row[1] for row in cur.fetchall()}
        assert 'business_id' in columns, "business_id 列不存在"
        assert 'name' in columns, "name 列不存在"
        assert 'description' in columns, "description 列不存在"
        assert 'status' in columns, "status 列不存在"

    print(f"✓ businesses 表结构正确: {list(columns.keys())}")

    conn.close()


def test_business_crud():
    """测试 business CRUD 操作。"""
    print("\n=== Test: Business CRUD ===")

    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False

    # 初始化表
    init_multi_tenancy_tables_with_conn(conn)

    # 创建 business
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO businesses (business_id, name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (business_id) DO NOTHING
            RETURNING business_id
        """, ("test_business_001", "测试业务", "这是一个测试业务"))
        result = cur.fetchone()
        conn.commit()
        if result:
            print("✓ Business 创建成功")
        else:
            print("✓ Business 已存在")

    # 获取 business
    with conn.cursor() as cur:
        cur.execute("""
            SELECT business_id, name, description, status
            FROM businesses WHERE business_id = %s
        """, ("test_business_001",))
        row = cur.fetchone()
        assert row is not None, "Business 不存在"
        assert row[0] == "test_business_001"
        assert row[1] == "测试业务"
        assert row[2] == "这是一个测试业务"
        assert row[3] == "active"
        print(f"✓ Business 获取成功: {row}")

    # 列出所有 businesses
    with conn.cursor() as cur:
        cur.execute("SELECT business_id, name FROM businesses")
        businesses = cur.fetchall()
        print(f"✓ 列出 {len(businesses)} 个 businesses")

    # 删除 business
    with conn.cursor() as cur:
        cur.execute("DELETE FROM businesses WHERE business_id = %s RETURNING business_id", ("test_business_001",))
        result = cur.fetchone()
        conn.commit()
        assert result is not None, "Business 删除失败"
        print("✓ Business 删除成功")

    conn.close()


def test_book_bindings_with_business():
    """测试 book_bindings 与 businesses 的外键关系。"""
    print("\n=== Test: Book Bindings with Business ===")

    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False

    # 初始化表
    init_multi_tenancy_tables_with_conn(conn)

    # 创建 book 和 business
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO books (book_id) VALUES (%s)
            ON CONFLICT (book_id) DO NOTHING
        """, ("test_bind_book_001",))
        cur.execute("""
            INSERT INTO businesses (business_id) VALUES (%s)
            ON CONFLICT (business_id) DO NOTHING
        """, ("test_bind_business_001",))
        conn.commit()
    print("✓ Book 和 Business 创建成功")

    # 创建绑定
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO book_bindings (business_id, book_id)
            VALUES (%s, %s)
            ON CONFLICT (business_id, book_id) DO NOTHING
        """, ("test_bind_business_001", "test_bind_book_001"))
        conn.commit()
    print("✓ 绑定创建成功")

    # 验证绑定
    with conn.cursor() as cur:
        cur.execute("""
            SELECT bb.business_id, bb.book_id, b.name as business_name
            FROM book_bindings bb
            JOIN businesses b ON bb.business_id = b.business_id
            WHERE bb.book_id = %s
        """, ("test_bind_book_001",))
        row = cur.fetchone()
        assert row is not None, "绑定不存在"
        print(f"✓ 绑定验证成功: business_id={row[0]}, book_id={row[1]}")

    # 测试级联删除
    with conn.cursor() as cur:
        cur.execute("DELETE FROM businesses WHERE business_id = %s", ("test_bind_business_001",))
        conn.commit()
    print("✓ Business 删除成功")

    # 验证绑定也被删除
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM book_bindings WHERE business_id = %s", ("test_bind_business_001",))
        count = cur.fetchone()[0]
        assert count == 0, "绑定没有被级联删除"
    print("✓ 绑定级联删除成功")

    # 清理
    with conn.cursor() as cur:
        cur.execute("DELETE FROM books WHERE book_id = %s", ("test_bind_book_001",))
        conn.commit()

    conn.close()


def main():
    print("=" * 60)
    print("Business Management Tests")
    print("=" * 60)

    try:
        test_businesses_table()
        test_business_crud()
        test_book_bindings_with_business()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
