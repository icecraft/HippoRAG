#!/usr/bin/env python3
"""
Multi-tenancy API test for HippoRAG.

Tests the book and business management endpoints:
- Book indexing
- Business binding
- Business queries (QA and retrieve)
- Data isolation between businesses
"""
import sys
import os
import time
import subprocess
import requests
import threading

# Add src to path
sys.path.insert(0, '/data2/git/HippoRAG/src')
from dotenv import load_dotenv
load_dotenv('/data2/git/HippoRAG/projects/.env')

API_URL = "http://127.0.0.1:8767"


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Wait for server to be ready."""
    for i in range(timeout):
        try:
            resp = requests.get(f'{url}/health', timeout=2)
            if resp.status_code == 200:
                return True
        except:
            time.sleep(1)
    return False


def test_book_index_sync():
    """Test book indexing endpoint."""
    print("\n=== Test: Book Index (Sync) ===")

    # Index book 1
    resp = requests.post(f'{API_URL}/book/index/sync', json={
        "book_id": "test_novel_001",
        "docs": [
            "方源一身残破的碧绿大袍，披头散发，浑身浴血，环顾四周。",
            "就这样紧张地对峙了三个时辰，夕阳西下。",
        ]
    }, timeout=180)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    assert data['book_id'] == 'test_novel_001'
    assert data['num_docs'] == 2
    print("✓ Book 1 indexed successfully")

    # Index book 2
    resp = requests.post(f'{API_URL}/book/index/sync', json={
        "book_id": "test_novel_002",
        "docs": [
            "张三穿着一件红色的长袍，站在城门口。",
            "他已经在那里站了一个时辰。",
        ]
    }, timeout=180)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    assert data['book_id'] == 'test_novel_002'
    print("✓ Book 2 indexed successfully")

    # Index book 3
    resp = requests.post(f'{API_URL}/book/index/sync', json={
        "book_id": "test_novel_003",
        "docs": [
            "李四穿着蓝色的衣服，坐在茶馆里。",
            "他已经在那里坐了两个时辰。",
        ]
    }, timeout=180)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    print("✓ Book 3 indexed successfully")


def test_list_books():
    """Test listing all books."""
    print("\n=== Test: List Books ===")

    resp = requests.get(f'{API_URL}/books')
    print(f"Response: {resp.json()}")

    assert resp.status_code == 200
    data = resp.json()
    assert 'books' in data
    book_ids = [b['book_id'] for b in data['books']]
    assert 'test_novel_001' in book_ids
    assert 'test_novel_002' in book_ids
    assert 'test_novel_003' in book_ids
    print(f"✓ Found {len(data['books'])} books")


def test_business_bind():
    """Test binding books to businesses."""
    print("\n=== Test: Business Bind ===")

    # Bind book 1 and 2 to business A
    resp = requests.post(f'{API_URL}/business/bind', json={
        "business_id": "test_business_a",
        "book_ids": ["test_novel_001", "test_novel_002"]
    })

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    assert 'test_novel_001' in data['book_ids']
    assert 'test_novel_002' in data['book_ids']
    print("✓ Business A bound to book 1 and 2")

    # Bind book 2 and 3 to business B
    resp = requests.post(f'{API_URL}/business/bind', json={
        "business_id": "test_business_b",
        "book_ids": ["test_novel_002", "test_novel_003"]
    })

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    assert 'test_novel_002' in data['book_ids']
    assert 'test_novel_003' in data['book_ids']
    print("✓ Business B bound to book 2 and 3")


def test_business_books():
    """Test listing books for a business."""
    print("\n=== Test: Business Books ===")

    resp = requests.get(f'{API_URL}/business/books?business_id=test_business_a')
    print(f"Response: {resp.json()}")

    assert resp.status_code == 200
    data = resp.json()
    assert data['business_id'] == 'test_business_a'
    book_ids = [b['book_id'] for b in data['books']]
    assert 'test_novel_001' in book_ids
    assert 'test_novel_002' in book_ids
    assert 'test_novel_003' not in book_ids  # Not bound to business A
    print(f"✓ Business A has {len(data['books'])} books")


def test_business_qa():
    """Test business QA endpoint."""
    print("\n=== Test: Business QA ===")

    # Business A should find info about 方源 and 张三
    resp = requests.post(f'{API_URL}/business/qa', json={
        "business_id": "test_business_a",
        "queries": ["方源穿的是什么颜色的袍子？"]
    }, timeout=60)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['business_id'] == 'test_business_a'
    assert len(data['results']) == 1

    result = data['results'][0]
    assert result['query'] == "方源穿的是什么颜色的袍子？"
    assert '碧绿' in result['answer'] or 'green' in result['answer'].lower()
    print(f"✓ Business A QA answer: {result['answer']}")

    # Business B should NOT find info about 方源
    resp = requests.post(f'{API_URL}/business/qa', json={
        "business_id": "test_business_b",
        "queries": ["方源穿的是什么颜色的袍子？"]
    }, timeout=60)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    result = data['results'][0]
    # Business B doesn't have book 1, so it shouldn't know about 方源
    print(f"  Business B answer for 方源: {result['answer']}")


def test_business_retrieve():
    """Test business retrieve endpoint."""
    print("\n=== Test: Business Retrieve ===")

    resp = requests.post(f'{API_URL}/business/retrieve', json={
        "business_id": "test_business_a",
        "queries": ["袍子"],
        "num_to_retrieve": 5,
        "return_scores": True
    }, timeout=60)

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['business_id'] == 'test_business_a'
    assert len(data['results']) == 1
    assert len(data['books_searched']) == 2  # book 1 and 2

    result = data['results'][0]
    assert len(result['passages']) > 0
    print(f"✓ Found {len(result['passages'])} passages")


def test_business_unbind():
    """Test unbinding books from business."""
    print("\n=== Test: Business Unbind ===")

    # Unbind book 2 from business A
    resp = requests.post(f'{API_URL}/business/unbind', json={
        "business_id": "test_business_a",
        "book_ids": ["test_novel_002"]
    })

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    print("✓ Book 2 unbound from business A")

    # Verify business A only has book 1 now
    resp = requests.get(f'{API_URL}/business/books?business_id=test_business_a')
    data = resp.json()
    book_ids = [b['book_id'] for b in data['books']]
    assert 'test_novel_001' in book_ids
    assert 'test_novel_002' not in book_ids
    print("✓ Business A now only has book 1")


def test_delete_book():
    """Test deleting a book."""
    print("\n=== Test: Delete Book ===")

    # Delete book 3
    resp = requests.delete(f'{API_URL}/book?book_id=test_novel_003')

    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'completed'
    print("✓ Book 3 deleted")

    # Verify book 3 is gone
    resp = requests.get(f'{API_URL}/books')
    data = resp.json()
    book_ids = [b['book_id'] for b in data['books']]
    assert 'test_novel_003' not in book_ids
    print("✓ Book 3 no longer in list")


def cleanup():
    """Clean up test data."""
    print("\n=== Cleanup ===")

    # Delete test books
    for book_id in ['test_novel_001', 'test_novel_002']:
        try:
            requests.delete(f'{API_URL}/book?book_id={book_id}')
            print(f"  Deleted {book_id}")
        except:
            pass


def main():
    print("=" * 60)
    print("HippoRAG Multi-Tenancy API Test")
    print("=" * 60)

    # Setup environment
    env = os.environ.copy()
    env['PYTHONPATH'] = '/data2/git/HippoRAG/src'

    # Start server
    print("\n启动 API 服务器...")
    server = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'hipporag.api:app',
         '--host', '127.0.0.1', '--port', '8767'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd='/data2/git/HippoRAG',
        env=env
    )

    def print_output():
        for line in iter(server.stdout.readline, b''):
            if b'ERROR' in line:
                print(f"[Server] {line.decode().strip()}")

    threading.Thread(target=print_output, daemon=True).start()

    # Wait for server
    print("等待服务器启动...")
    if not wait_for_server(API_URL, timeout=60):
        print("❌ 服务器启动失败!")
        server.terminate()
        return 1

    print("✓ 服务器就绪!\n")

    try:
        # Run tests
        test_book_index_sync()
        test_list_books()
        test_business_bind()
        test_business_books()
        test_business_qa()
        test_business_retrieve()
        test_business_unbind()
        test_delete_book()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cleanup()
        server.terminate()
        print("\n服务器已停止")

    return 0


if __name__ == "__main__":
    exit(main())
