#!/usr/bin/env python3
"""
Unit tests for multi-tenancy database operations.

Tests the MultiTenancyDB class without requiring a full HippoRAG setup.
"""
import sys
import os

sys.path.insert(0, '/data2/git/HippoRAG/src')
from dotenv import load_dotenv
load_dotenv('/data2/git/HippoRAG/projects/.env')

from hipporag.multi_tenancy.database import MultiTenancyDB


def get_db_config():
    """Get database configuration from environment."""
    return {
        'host': os.getenv('PGVECTOR_HOST', 'localhost'),
        'port': int(os.getenv('PGVECTOR_PORT', '5432')),
        'database': os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        'user': os.getenv('PGVECTOR_USER', 'postgres'),
        'password': os.getenv('PGVECTOR_PASSWORD', ''),
    }


def test_database_connection():
    """Test database connection and table creation."""
    print("\n=== Test: Database Connection ===")

    db_config = get_db_config()
    db = MultiTenancyDB(db_config)

    assert db.conn is not None
    print("✓ Connected to database")

    # Check tables exist
    with db.conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name IN ('books', 'book_bindings')
        """)
        tables = [row[0] for row in cur.fetchall()]
        assert 'books' in tables
        assert 'book_bindings' in tables

    print("✓ Tables exist")
    db.close()


def test_book_crud():
    """Test book CRUD operations."""
    print("\n=== Test: Book CRUD ===")

    db = MultiTenancyDB(get_db_config())

    # Create book
    created = db.create_book("test_book_001")
    assert created or db.book_exists("test_book_001")  # May already exist
    print("✓ Book created")

    # Get book
    book = db.get_book("test_book_001")
    assert book is not None
    assert book['book_id'] == "test_book_001"
    assert book['status'] == "ready"
    print(f"✓ Book retrieved: {book}")

    # List books
    books = db.list_books()
    assert len(books) > 0
    book_ids = [b['book_id'] for b in books]
    assert "test_book_001" in book_ids
    print(f"✓ Listed {len(books)} books")

    # Update doc count
    db.update_book_doc_count("test_book_001", 100)
    book = db.get_book("test_book_001")
    assert book['doc_count'] == 100
    print("✓ Doc count updated")

    # Delete book
    deleted = db.delete_book("test_book_001")
    assert deleted
    assert not db.book_exists("test_book_001")
    print("✓ Book deleted")

    db.close()


def test_binding_operations():
    """Test business binding operations."""
    print("\n=== Test: Binding Operations ===")

    db = MultiTenancyDB(get_db_config())

    # Create test books
    db.create_book("test_binding_book_1")
    db.create_book("test_binding_book_2")
    db.create_book("test_binding_book_3")
    print("✓ Test books created")

    # Bind books to business A
    bound = db.bind_books("test_business_001", ["test_binding_book_1", "test_binding_book_2"])
    assert bound == 2
    print(f"✓ Bound {bound} books to business A")

    # Bind books to business B (overlapping with A)
    bound = db.bind_books("test_business_002", ["test_binding_book_2", "test_binding_book_3"])
    assert bound == 2
    print(f"✓ Bound {bound} books to business B")

    # Get books by business
    books_a = db.get_books_by_business("test_business_001")
    assert len(books_a) == 2
    book_ids_a = [b['book_id'] for b in books_a]
    assert "test_binding_book_1" in book_ids_a
    assert "test_binding_book_2" in book_ids_a
    assert "test_binding_book_3" not in book_ids_a  # Not bound to A
    print(f"✓ Business A has {len(books_a)} books")

    books_b = db.get_books_by_business("test_business_002")
    assert len(books_b) == 2
    print(f"✓ Business B has {len(books_b)} books")

    # Get book IDs by business
    book_ids = db.get_book_ids_by_business("test_business_001")
    assert len(book_ids) == 2
    print(f"✓ Got {len(book_ids)} book IDs for business A")

    # Get businesses by book
    businesses = db.get_businesses_by_book("test_binding_book_2")
    assert len(businesses) == 2  # Shared between A and B
    assert "test_business_001" in businesses
    assert "test_business_002" in businesses
    print(f"✓ Book 2 is shared by {len(businesses)} businesses")

    # Unbind book
    unbound = db.unbind_books("test_business_001", ["test_binding_book_2"])
    assert unbound == 1
    books_a = db.get_books_by_business("test_business_001")
    assert len(books_a) == 1
    assert books_a[0]['book_id'] == "test_binding_book_1"
    print(f"✓ Unbound book, business A now has {len(books_a)} book")

    # Cleanup
    db.delete_book("test_binding_book_1")
    db.delete_book("test_binding_book_2")
    db.delete_book("test_binding_book_3")
    print("✓ Test books deleted")

    db.close()


def test_cascade_delete():
    """Test that deleting a book removes its bindings."""
    print("\n=== Test: Cascade Delete ===")

    db = MultiTenancyDB(get_db_config())

    # Create book and bind to business
    db.create_book("test_cascade_book")
    db.bind_books("test_cascade_business", ["test_cascade_book"])
    print("✓ Book created and bound")

    # Verify binding exists
    books = db.get_books_by_business("test_cascade_business")
    assert len(books) == 1
    print("✓ Binding exists")

    # Delete book
    db.delete_book("test_cascade_book")
    print("✓ Book deleted")

    # Verify binding is gone
    books = db.get_books_by_business("test_cascade_business")
    assert len(books) == 0
    print("✓ Binding cascade deleted")

    db.close()


def test_duplicate_binding():
    """Test that duplicate bindings are handled correctly."""
    print("\n=== Test: Duplicate Binding ===")

    db = MultiTenancyDB(get_db_config())

    # Create book
    db.create_book("test_dup_book")
    print("✓ Book created")

    # Bind same book twice
    bound1 = db.bind_books("test_dup_business", ["test_dup_book"])
    bound2 = db.bind_books("test_dup_business", ["test_dup_book"])  # Duplicate

    assert bound1 == 1
    assert bound2 == 0  # No new binding created
    print(f"✓ First bind: {bound1}, Second bind: {bound2}")

    # Verify only one binding exists
    books = db.get_books_by_business("test_dup_business")
    assert len(books) == 1
    print("✓ Only one binding exists")

    # Cleanup
    db.delete_book("test_dup_book")
    db.close()


def main():
    print("=" * 60)
    print("Multi-Tenancy Database Unit Tests")
    print("=" * 60)

    try:
        test_database_connection()
        test_book_crud()
        test_binding_operations()
        test_cascade_delete()
        test_duplicate_binding()

        print("\n" + "=" * 60)
        print("✓ All database tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
