"""
Multi-tenancy manager for HippoRAG.

Manages multiple book instances and provides unified query interface
for businesses that can access multiple books.
"""

import logging
import os
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .database import MultiTenancyDB
from ..HippoRAG import HippoRAG
from ..utils.config_utils import BaseConfig

logger = logging.getLogger(__name__)


class MultiTenancyManager:
    """
    Manager for multi-tenancy support.

    Responsibilities:
    - Manage HippoRAG instances per book
    - Handle book indexing
    - Handle business queries across multiple books
    - Manage book-business bindings

    Note: Currently uses book_id for embedding isolation in PostgreSQL.
    DGraph data is shared across all books in the same DGraph instance.
    """

    def __init__(self, base_config: BaseConfig):
        """
        Initialize the multi-tenancy manager.

        Parameters:
            base_config: Base configuration for HippoRAG instances
        """
        self.base_config = base_config
        self.db = self._init_db()
        self._book_instances: Dict[str, HippoRAG] = {}

    def _init_db(self) -> MultiTenancyDB:
        """Initialize the database connection."""
        db_config = {
            'host': self.base_config.pgvector_host,
            'port': self.base_config.pgvector_port,
            'database': self.base_config.pgvector_database,
            'user': self.base_config.pgvector_user,
            'password': self.base_config.pgvector_password
        }
        return MultiTenancyDB(db_config)

    def _get_book_config(self, book_id: str) -> BaseConfig:
        """
        Create a configuration for a specific book.

        The book_id is used to:
        - Filter embeddings by book_id in PostgreSQL
        - Create isolated save directory for book-specific files
        """
        config = BaseConfig(
            save_dir=os.path.join(self.base_config.save_dir, f"book_{book_id}"),
            # Copy LLM/Embedding settings
            llm_base_url=self.base_config.llm_base_url,
            llm_name=self.base_config.llm_name,
            embedding_model_name=self.base_config.embedding_model_name,
            embedding_base_url=self.base_config.embedding_base_url,
            embedding_batch_size=self.base_config.embedding_batch_size,
            # Copy DGraph settings (shared across books)
            graph_library="dgraph",
            dgraph_config=self.base_config.dgraph_config,
            # Copy pgvector settings
            use_pgvector=True,
            pgvector_host=self.base_config.pgvector_host,
            pgvector_port=self.base_config.pgvector_port,
            pgvector_database=self.base_config.pgvector_database,
            pgvector_user=self.base_config.pgvector_user,
            pgvector_password=self.base_config.pgvector_password,
            # Add book_id to embeddings for isolation
            book_id=book_id,
        )
        return config

    def _get_or_create_book_instance(self, book_id: str) -> HippoRAG:
        """
        Get or create a HippoRAG instance for a book.

        Instances are cached to avoid recreating them for each request.
        """
        if book_id not in self._book_instances:
            # Ensure book exists in database
            if not self.db.book_exists(book_id):
                self.db.create_book(book_id)

            config = self._get_book_config(book_id)
            self._book_instances[book_id] = HippoRAG(global_config=config)
            logger.info(f"Created HippoRAG instance for book {book_id}")

        return self._book_instances[book_id]

    def _remove_book_instance(self, book_id: str):
        """Remove a book instance from cache."""
        if book_id in self._book_instances:
            del self._book_instances[book_id]
            logger.info(f"Removed HippoRAG instance for book {book_id}")

    # ==================== Book Operations ====================

    def index_book(self, book_id: str, docs: List[str]) -> Dict:
        """
        Index documents into a book.

        Parameters:
            book_id: Book identifier
            docs: List of documents to index

        Returns:
            Dict with status and message
        """
        if not docs:
            return {'status': 'error', 'message': 'No documents provided'}

        try:
            # Create book record if not exists
            self.db.create_book(book_id)

            # Get or create book instance
            hipporag = self._get_or_create_book_instance(book_id)

            # Index documents
            hipporag.index(docs=docs)

            # Update doc count
            self.db.update_book_doc_count(book_id, len(docs))

            return {
                'status': 'completed',
                'message': f'Successfully indexed {len(docs)} documents',
                'book_id': book_id,
                'num_docs': len(docs)
            }
        except Exception as e:
            logger.error(f"Failed to index book {book_id}: {e}")
            return {
                'status': 'failed',
                'message': str(e),
                'book_id': book_id,
                'num_docs': 0
            }

    def get_book(self, book_id: str) -> Optional[Dict]:
        """Get book metadata."""
        return self.db.get_book(book_id)

    def list_books(self) -> List[Dict]:
        """List all books."""
        return self.db.list_books()

    def delete_book(self, book_id: str) -> Dict:
        """
        Delete a book and all its data.

        This removes:
        - Book bindings from database
        - Book record from database
        - DGraph predicates for this book
        - Embeddings for this book
        - HippoRAG instance from cache
        """
        try:
            # Get the HippoRAG instance to clean up its data
            if book_id in self._book_instances:
                hipporag = self._book_instances[book_id]
                # TODO: Add cleanup methods to HippoRAG for DGraph and embeddings

            # Remove from cache
            self._remove_book_instance(book_id)

            # Delete from database (cascade will remove bindings)
            deleted = self.db.delete_book(book_id)

            if deleted:
                return {'status': 'completed', 'message': f'Book {book_id} deleted'}
            else:
                return {'status': 'not_found', 'message': f'Book {book_id} not found'}
        except Exception as e:
            logger.error(f"Failed to delete book {book_id}: {e}")
            return {'status': 'failed', 'message': str(e)}

    # ==================== Business Binding Operations ====================

    def bind_books(self, business_id: str, book_ids: List[str]) -> Dict:
        """
        Bind books to a business.

        Parameters:
            business_id: Business identifier
            book_ids: List of book IDs to bind

        Returns:
            Dict with status and bound book IDs
        """
        if not book_ids:
            return {
                'status': 'error',
                'message': 'No book IDs provided',
                'business_id': business_id,
                'book_ids': []
            }

        try:
            bound_count = self.db.bind_books(business_id, book_ids)

            # Get the actual bound books
            bound_books = self.db.get_book_ids_by_business(business_id)

            return {
                'status': 'completed',
                'message': f'Successfully bound {bound_count} books to business',
                'business_id': business_id,
                'book_ids': bound_books
            }
        except Exception as e:
            logger.error(f"Failed to bind books to {business_id}: {e}")
            return {
                'status': 'failed',
                'message': str(e),
                'business_id': business_id,
                'book_ids': []
            }

    def unbind_books(self, business_id: str, book_ids: List[str]) -> Dict:
        """
        Unbind books from a business.

        Parameters:
            business_id: Business identifier
            book_ids: List of book IDs to unbind

        Returns:
            Dict with status
        """
        if not book_ids:
            return {
                'status': 'error',
                'message': 'No book IDs provided',
                'business_id': business_id
            }

        try:
            unbound_count = self.db.unbind_books(business_id, book_ids)

            return {
                'status': 'completed',
                'message': f'Successfully unbound {unbound_count} books from business',
                'business_id': business_id,
                'unbound_count': unbound_count
            }
        except Exception as e:
            logger.error(f"Failed to unbind books from {business_id}: {e}")
            return {
                'status': 'failed',
                'message': str(e),
                'business_id': business_id
            }

    def get_business_books(self, business_id: str) -> Dict:
        """
        Get all books bound to a business.

        Returns:
            Dict with business_id and list of books
        """
        books = self.db.get_books_by_business(business_id)
        return {
            'business_id': business_id,
            'books': books
        }

    # ==================== Business Query Operations ====================

    def retrieve_by_business(
        self,
        business_id: str,
        queries: List[str],
        num_to_retrieve: int = None,
        return_scores: bool = False
    ) -> Dict:
        """
        Retrieve passages from all books bound to a business.

        Parameters:
            business_id: Business identifier
            queries: List of queries
            num_to_retrieve: Number of passages to retrieve per book
            return_scores: Whether to return retrieval scores

        Returns:
            Dict with results from all books
        """
        book_ids = self.db.get_book_ids_by_business(business_id)

        if not book_ids:
            return {
                'results': [{
                    'query': q,
                    'passages': [],
                    'scores': None,
                    'book_id': None
                } for q in queries],
                'business_id': business_id,
                'books_searched': []
            }

        all_results = []

        # Retrieve from each book in parallel
        with ThreadPoolExecutor(max_workers=min(len(book_ids), 5)) as executor:
            futures = {}
            for book_id in book_ids:
                try:
                    hipporag = self._get_or_create_book_instance(book_id)
                    future = executor.submit(
                        hipporag.retrieve,
                        queries,
                        num_to_retrieve
                    )
                    futures[future] = book_id
                except Exception as e:
                    logger.error(f"Failed to retrieve from book {book_id}: {e}")

            for future in as_completed(futures):
                book_id = futures[future]
                try:
                    results = future.result()
                    if isinstance(results, tuple):
                        query_solutions, _ = results
                    else:
                        query_solutions = results
                    all_results.append((book_id, query_solutions))
                except Exception as e:
                    logger.error(f"Failed to get results from book {book_id}: {e}")

        # Merge results by query
        merged_results = []
        for i, query in enumerate(queries):
            passages = []
            scores = []

            for book_id, query_solutions in all_results:
                if i < len(query_solutions):
                    qs = query_solutions[i]
                    if hasattr(qs, 'docs') and qs.docs:
                        for doc in qs.docs:
                            passages.append({
                                'content': str(doc),
                                'doc_id': None,
                                'book_id': book_id
                            })

                    if return_scores and hasattr(qs, 'doc_scores') and qs.doc_scores is not None:
                        import numpy as np
                        if isinstance(qs.doc_scores, np.ndarray):
                            scores.extend(qs.doc_scores.tolist())

            merged_results.append({
                'query': query,
                'passages': passages,
                'scores': scores if return_scores and scores else None
            })

        return {
            'results': merged_results,
            'business_id': business_id,
            'books_searched': book_ids
        }

    def qa_by_business(
        self,
        business_id: str,
        queries: List[str],
        num_to_retrieve: int = None
    ) -> Dict:
        """
        Answer questions using all books bound to a business.

        This performs retrieval from all books and then uses LLM to answer.

        Parameters:
            business_id: Business identifier
            queries: List of questions
            num_to_retrieve: Number of passages to retrieve per book

        Returns:
            Dict with QA results
        """
        book_ids = self.db.get_book_ids_by_business(business_id)

        if not book_ids:
            return {
                'results': [{
                    'query': q,
                    'answer': 'No books are bound to this business',
                    'passages': [],
                    'book_id': None
                } for q in queries],
                'business_id': business_id,
                'books_searched': []
            }

        # For now, we'll retrieve from all books and use the first book's
        # HippoRAG instance for QA (the passages will come from all books)
        # This is a simplified approach; a more sophisticated approach would
        # merge the contexts before QA

        all_passages_by_query = [[] for _ in queries]
        source_book_ids = [None for _ in queries]

        # Retrieve from each book
        with ThreadPoolExecutor(max_workers=min(len(book_ids), 5)) as executor:
            futures = {}
            for book_id in book_ids:
                try:
                    hipporag = self._get_or_create_book_instance(book_id)
                    future = executor.submit(
                        hipporag.retrieve,
                        queries,
                        num_to_retrieve
                    )
                    futures[future] = book_id
                except Exception as e:
                    logger.error(f"Failed to retrieve from book {book_id}: {e}")

            for future in as_completed(futures):
                book_id = futures[future]
                try:
                    results = future.result()
                    if isinstance(results, tuple):
                        query_solutions, _ = results
                    else:
                        query_solutions = results

                    for i, qs in enumerate(query_solutions):
                        if hasattr(qs, 'docs') and qs.docs:
                            for doc in qs.docs:
                                all_passages_by_query[i].append({
                                    'content': str(doc),
                                    'book_id': book_id
                                })
                            if source_book_ids[i] is None:
                                source_book_ids[i] = book_id
                except Exception as e:
                    logger.error(f"Failed to get results from book {book_id}: {e}")

        # Use the first available book's instance for QA
        qa_instance = None
        for book_id in book_ids:
            try:
                qa_instance = self._get_or_create_book_instance(book_id)
                break
            except:
                continue

        if qa_instance is None:
            return {
                'results': [{
                    'query': q,
                    'answer': 'Failed to initialize QA engine',
                    'passages': all_passages_by_query[i],
                    'book_id': source_book_ids[i]
                } for i, q in enumerate(queries)],
                'business_id': business_id,
                'books_searched': book_ids
            }

        # Perform QA using the combined context
        # For simplicity, we'll use the first book's QA engine
        # and create QuerySolution objects with the combined passages
        results = []
        for i, query in enumerate(queries):
            try:
                # Create a simple query solution with the combined passages
                from ..utils.misc_utils import QuerySolution

                # Build combined docs string for context
                combined_docs = [p['content'] for p in all_passages_by_query[i]]

                if not combined_docs:
                    results.append({
                        'query': query,
                        'answer': 'No relevant information found',
                        'passages': [],
                        'book_id': None
                    })
                    continue

                # Use the QA engine directly
                qa_results = qa_instance.rag_qa(queries=[QuerySolution(question=query, docs=combined_docs)])

                if isinstance(qa_results, tuple):
                    _, answers, _ = qa_results
                else:
                    answers = qa_results

                answer = answers[0] if answers else "Could not generate answer"

                results.append({
                    'query': query,
                    'answer': answer,
                    'passages': all_passages_by_query[i],
                    'book_id': source_book_ids[i]
                })
            except Exception as e:
                logger.error(f"QA failed for query '{query}': {e}")
                results.append({
                    'query': query,
                    'answer': f'Error: {str(e)}',
                    'passages': all_passages_by_query[i],
                    'book_id': source_book_ids[i]
                })

        return {
            'results': results,
            'business_id': business_id,
            'books_searched': book_ids
        }

    def close(self):
        """Close all connections and cleanup."""
        for book_id, instance in self._book_instances.items():
            try:
                # HippoRAG may have cleanup methods
                pass
            except:
                pass
        self._book_instances.clear()
        self.db.close()
