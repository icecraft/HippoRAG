"""
Database operations for multi-tenancy support.

Handles book_bindings and books tables for managing the many-to-many
relationship between businesses and books.
"""

import logging
import os
from typing import List, Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


class MultiTenancyDB:
    """
    Database manager for multi-tenancy support.

    Manages:
    - books: Book metadata (book_id, doc_count, status, etc.)
    - book_bindings: Many-to-many relationship between businesses and books
    """

    def __init__(self, db_config: Dict):
        """
        Initialize the database connection and create tables.

        Parameters:
            db_config: PostgreSQL connection config dict with keys:
                - host: PostgreSQL host
                - port: PostgreSQL port
                - database: Database name
                - user: Username
                - password: Password
        """
        self.db_config = db_config
        self.conn = None
        self._connect()
        self._init_tables()

    def _connect(self):
        """Connect to PostgreSQL."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = False
            logger.info("Connected to PostgreSQL for multi-tenancy")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def _init_tables(self):
        """Initialize the multi-tenancy tables."""
        with self.conn.cursor() as cur:
            # Check if books table exists and has correct schema
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'books'
            """)
            existing_columns = [row[0] for row in cur.fetchall()]

            # If books table exists but doesn't have book_id, rename it
            if existing_columns and 'book_id' not in existing_columns:
                logger.warning("Existing 'books' table doesn't have book_id column, renaming to books_old")
                cur.execute("DROP TABLE IF EXISTS books_old")
                cur.execute("ALTER TABLE books RENAME TO books_old")

            # Create books table with correct schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id VARCHAR(64) PRIMARY KEY,
                    doc_count INT DEFAULT 0,
                    status VARCHAR(16) DEFAULT 'ready',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Check if book_bindings table exists and has correct schema
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'book_bindings'
            """)
            binding_columns = [row[0] for row in cur.fetchall()]

            # If book_bindings table exists but doesn't have correct schema, drop it
            if binding_columns and 'book_id' not in binding_columns:
                logger.warning("Existing 'book_bindings' table doesn't have correct schema, dropping")
                cur.execute("DROP TABLE IF EXISTS book_bindings CASCADE")

            # Create book_bindings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS book_bindings (
                    id SERIAL PRIMARY KEY,
                    business_id VARCHAR(64) NOT NULL,
                    book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(business_id, book_id)
                );
            """)

            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_business
                ON book_bindings(business_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_book
                ON book_bindings(book_id);
            """)

            self.conn.commit()
            logger.info("Multi-tenancy tables initialized")

    # ==================== Book Operations ====================

    def create_book(self, book_id: str) -> bool:
        """
        Create a new book record.

        Parameters:
            book_id: Unique book identifier

        Returns:
            True if created, False if already exists
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO books (book_id, status)
                    VALUES (%s, 'ready')
                    ON CONFLICT (book_id) DO NOTHING
                    RETURNING book_id
                """, (book_id,))
                result = cur.fetchone()
                self.conn.commit()
                return result is not None
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating book {book_id}: {e}")
            raise

    def get_book(self, book_id: str) -> Optional[Dict]:
        """Get book metadata."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT book_id, doc_count, status, created_at, updated_at
                FROM books WHERE book_id = %s
            """, (book_id,))
            row = cur.fetchone()
            if row:
                return {
                    'book_id': row[0],
                    'doc_count': row[1],
                    'status': row[2],
                    'created_at': row[3].isoformat() if row[3] else None,
                    'updated_at': row[4].isoformat() if row[4] else None
                }
            return None

    def list_books(self) -> List[Dict]:
        """List all books."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT book_id, doc_count, status, created_at, updated_at
                FROM books ORDER BY created_at DESC
            """)
            return [{
                'book_id': row[0],
                'doc_count': row[1],
                'status': row[2],
                'created_at': row[3].isoformat() if row[3] else None,
                'updated_at': row[4].isoformat() if row[4] else None
            } for row in cur.fetchall()]

    def update_book_doc_count(self, book_id: str, doc_count: int):
        """Update book document count."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE books
                    SET doc_count = %s, updated_at = NOW()
                    WHERE book_id = %s
                """, (doc_count, book_id))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating book {book_id}: {e}")
            raise

    def delete_book(self, book_id: str) -> bool:
        """
        Delete a book and all its bindings.

        Returns:
            True if deleted, False if not found
        """
        try:
            with self.conn.cursor() as cur:
                # First delete all bindings (cascade should handle this, but be explicit)
                cur.execute("DELETE FROM book_bindings WHERE book_id = %s", (book_id,))
                # Then delete the book
                cur.execute("DELETE FROM books WHERE book_id = %s RETURNING book_id", (book_id,))
                result = cur.fetchone()
                self.conn.commit()
                return result is not None
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error deleting book {book_id}: {e}")
            raise

    def book_exists(self, book_id: str) -> bool:
        """Check if a book exists."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM books WHERE book_id = %s", (book_id,))
            return cur.fetchone() is not None

    # ==================== Binding Operations ====================

    def bind_books(self, business_id: str, book_ids: List[str]) -> int:
        """
        Bind books to a business.

        Parameters:
            business_id: Business identifier
            book_ids: List of book IDs to bind

        Returns:
            Number of books actually bound (excluding existing bindings)
        """
        if not book_ids:
            return 0

        try:
            with self.conn.cursor() as cur:
                # Filter out books that don't exist
                placeholders = ','.join(['%s'] * len(book_ids))
                cur.execute(f"""
                    SELECT book_id FROM books WHERE book_id IN ({placeholders})
                """, book_ids)
                existing_books = [row[0] for row in cur.fetchall()]

                if not existing_books:
                    logger.warning(f"No valid books found for binding to {business_id}")
                    return 0

                # Insert bindings
                data = [(business_id, book_id) for book_id in existing_books]
                execute_values(
                    cur,
                    """
                    INSERT INTO book_bindings (business_id, book_id)
                    VALUES %s
                    ON CONFLICT (business_id, book_id) DO NOTHING
                    """,
                    data
                )
                bound_count = cur.rowcount
                self.conn.commit()
                logger.info(f"Bound {bound_count} books to business {business_id}")
                return bound_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error binding books to {business_id}: {e}")
            raise

    def unbind_books(self, business_id: str, book_ids: List[str]) -> int:
        """
        Unbind books from a business.

        Parameters:
            business_id: Business identifier
            book_ids: List of book IDs to unbind

        Returns:
            Number of bindings removed
        """
        if not book_ids:
            return 0

        try:
            with self.conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(book_ids))
                cur.execute(f"""
                    DELETE FROM book_bindings
                    WHERE business_id = %s AND book_id IN ({placeholders})
                """, [business_id] + book_ids)
                deleted_count = cur.rowcount
                self.conn.commit()
                logger.info(f"Unbound {deleted_count} books from business {business_id}")
                return deleted_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error unbinding books from {business_id}: {e}")
            raise

    def get_books_by_business(self, business_id: str) -> List[Dict]:
        """
        Get all books bound to a business.

        Returns:
            List of book metadata dicts
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT b.book_id, b.doc_count, b.status, b.created_at, b.updated_at
                FROM books b
                INNER JOIN book_bindings bb ON b.book_id = bb.book_id
                WHERE bb.business_id = %s
                ORDER BY b.created_at DESC
            """, (business_id,))
            return [{
                'book_id': row[0],
                'doc_count': row[1],
                'status': row[2],
                'created_at': row[3].isoformat() if row[3] else None,
                'updated_at': row[4].isoformat() if row[4] else None
            } for row in cur.fetchall()]

    def get_book_ids_by_business(self, business_id: str) -> List[str]:
        """
        Get all book IDs bound to a business.

        Returns:
            List of book_id strings
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT book_id FROM book_bindings
                WHERE business_id = %s
            """, (business_id,))
            return [row[0] for row in cur.fetchall()]

    def get_businesses_by_book(self, book_id: str) -> List[str]:
        """
        Get all businesses that have access to a book.

        Returns:
            List of business_id strings
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT business_id FROM book_bindings
                WHERE book_id = %s
            """, (book_id,))
            return [row[0] for row in cur.fetchall()]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Closed multi-tenancy database connection")

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
