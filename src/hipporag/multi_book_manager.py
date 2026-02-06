"""
Multi-Book Manager for HippoRAG

This module provides a MultiBookHippoRAG class for managing multiple books
in separate HippoRAG instances, allowing for organized indexing and querying
across multiple document collections.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict

from .HippoRAG import HippoRAG
from .utils.config_utils import BaseConfig
from .utils.misc_utils import QuerySolution

logger = logging.getLogger(__name__)


class MultiBookHippoRAG:
    """
    Manager for multiple books, each stored in a separate HippoRAG instance.
    
    This class allows you to:
    - Index multiple books separately
    - Query individual books
    - Query across multiple books
    - Manage book metadata and information
    
    Example:
        >>> from hipporag import MultiBookHippoRAG
        >>> from hipporag.utils.config_utils import BaseConfig
        >>> 
        >>> config = BaseConfig(
        ...     save_dir='outputs/multi_books',
        ...     llm_name='gpt-4o-mini',
        ...     embedding_model_name='text-embedding-3-small',
        ... )
        >>> 
        >>> manager = MultiBookHippoRAG(base_config=config)
        >>> manager.add_book("book1", ["Chapter 1...", "Chapter 2..."])
        >>> manager.add_book("book2", ["Chapter 1...", "Chapter 2..."])
        >>> 
        >>> # Query single book
        >>> results = manager.query_single_book("book1", "What happened?")
        >>> 
        >>> # Query multiple books
        >>> results = manager.query("What happened?", book_ids=["book1", "book2"])
    """
    
    def __init__(self, 
                 base_config: BaseConfig, 
                 base_save_dir: Optional[str] = None,
                 # pgvector configuration (optional overrides)
                 pgvector_host: Optional[str] = None,
                 pgvector_port: Optional[int] = None,
                 pgvector_database: Optional[str] = None,
                 pgvector_user: Optional[str] = None,
                 pgvector_password: Optional[str] = None,
                 pgvector_index_type: Optional[str] = None,
                 pgvector_index_lists: Optional[int] = None,
                 # Nebula Graph configuration (optional overrides)
                 nebula_host: Optional[str] = None,
                 nebula_port: Optional[int] = None,
                 nebula_user: Optional[str] = None,
                 nebula_password: Optional[str] = None,
                 nebula_space_name: Optional[str] = None):
        """
        Initialize the multi-book manager.
        
        Parameters:
            base_config: BaseConfig
                Base configuration to use for all books. Each book will have its own
                save directory under the base save_dir.
            base_save_dir: str, optional
                Base directory for saving book indices. If None, uses base_config.save_dir.
                Each book will be saved in a subdirectory: {base_save_dir}/{book_id}
            pgvector_host: str, optional
                PostgreSQL host (overrides base_config if provided)
            pgvector_port: int, optional
                PostgreSQL port (overrides base_config if provided)
            pgvector_database: str, optional
                PostgreSQL database name (overrides base_config if provided)
            pgvector_user: str, optional
                PostgreSQL user (overrides base_config if provided)
            pgvector_password: str, optional
                PostgreSQL password (overrides base_config if provided)
            pgvector_index_type: str, optional
                Vector index type (overrides base_config if provided)
            pgvector_index_lists: int, optional
                Number of lists for IVFFlat index (overrides base_config if provided)
            nebula_host: str, optional
                Nebula Graph host (overrides base_config if provided)
            nebula_port: int, optional
                Nebula Graph port (overrides base_config if provided)
            nebula_user: str, optional
                Nebula Graph user (overrides base_config if provided)
            nebula_password: str, optional
                Nebula Graph password (overrides base_config if provided)
            nebula_space_name: str, optional
                Nebula Graph space name (overrides base_config if provided)
        """
        self.base_config = base_config
        self.base_save_dir = base_save_dir or base_config.save_dir
        self.books: Dict[str, HippoRAG] = {}
        self.book_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Store pgvector overrides
        self.pgvector_overrides = {
            'host': pgvector_host,
            'port': pgvector_port,
            'database': pgvector_database,
            'user': pgvector_user,
            'password': pgvector_password,
            'index_type': pgvector_index_type,
            'index_lists': pgvector_index_lists
        }
        
        # Store Nebula Graph overrides
        self.nebula_overrides = {
            'host': nebula_host,
            'port': nebula_port,
            'user': nebula_user,
            'password': nebula_password,
            'space_name': nebula_space_name
        }
        
        # Ensure base directory exists
        if not os.path.exists(self.base_save_dir):
            os.makedirs(self.base_save_dir, exist_ok=True)
            logger.info("Created base directory: %s", self.base_save_dir)
    
    def add_book(self, 
                 book_id: str, 
                 chapters: List[str],
                 force_index_from_scratch: bool = False,
                 force_openie_from_scratch: bool = False,
                 metadata: Optional[Dict[str, Any]] = None) -> HippoRAG:
        """
        Add and index a book.
        
        Parameters:
            book_id: str
                Unique identifier for the book (e.g., "book1", "novel_001")
            chapters: List[str]
                List of chapter/document strings to index
            force_index_from_scratch: bool, default=False
                If True, rebuild index from scratch (ignores existing index)
            force_openie_from_scratch: bool, default=False
                If True, rebuild OpenIE results from scratch
            metadata: Dict[str, Any], optional
                Optional metadata for the book (e.g., {"title": "...", "author": "..."})
        
        Returns:
            HippoRAG: The HippoRAG instance for this book
        
        Raises:
            ValueError: If book_id already exists
        """
        if book_id in self.books:
            raise ValueError(f"Book '{book_id}' already exists. Use update_book() or remove_book() first.")
        
        logger.info("Adding book '%s' with %d chapters", book_id, len(chapters))
        
        # Create book-specific config
        book_config = BaseConfig(**asdict(self.base_config))
        book_config.save_dir = os.path.join(self.base_save_dir, book_id)
        book_config.force_index_from_scratch = force_index_from_scratch
        book_config.force_openie_from_scratch = force_openie_from_scratch
        book_config.corpus_len = len(chapters)
        
        # Apply pgvector overrides if provided
        if self.pgvector_overrides['host'] is not None:
            book_config.pgvector_host = self.pgvector_overrides['host']
        if self.pgvector_overrides['port'] is not None:
            book_config.pgvector_port = self.pgvector_overrides['port']
        if self.pgvector_overrides['database'] is not None:
            book_config.pgvector_database = self.pgvector_overrides['database']
        if self.pgvector_overrides['user'] is not None:
            book_config.pgvector_user = self.pgvector_overrides['user']
        if self.pgvector_overrides['password'] is not None:
            book_config.pgvector_password = self.pgvector_overrides['password']
        if self.pgvector_overrides['index_type'] is not None:
            book_config.pgvector_index_type = self.pgvector_overrides['index_type']
        if self.pgvector_overrides['index_lists'] is not None:
            book_config.pgvector_index_lists = self.pgvector_overrides['index_lists']
        
        # Apply Nebula Graph overrides if provided
        if self.nebula_overrides['host'] is not None:
            book_config.nebula_host = self.nebula_overrides['host']
        if self.nebula_overrides['port'] is not None:
            book_config.nebula_port = self.nebula_overrides['port']
        if self.nebula_overrides['user'] is not None:
            book_config.nebula_user = self.nebula_overrides['user']
        if self.nebula_overrides['password'] is not None:
            book_config.nebula_password = self.nebula_overrides['password']
        if self.nebula_overrides['space_name'] is not None:
            # For multi-book, use book_id as suffix to space name for isolation
            base_space = self.nebula_overrides['space_name']
            book_config.nebula_space_name = f"{base_space}_{book_id}"
        
        # Create HippoRAG instance for this book
        hipporag = HippoRAG(global_config=book_config)
        
        # Index the chapters
        logger.info("Indexing %d chapters for book '%s'...", len(chapters), book_id)
        hipporag.index(docs=chapters)
        
        # Store the instance and metadata
        self.books[book_id] = hipporag
        self.book_metadata[book_id] = {
            'num_chapters': len(chapters),
            'total_chars': sum(len(ch) for ch in chapters),
            **(metadata or {})
        }
        
        logger.info("Successfully added book '%s'", book_id)
        return hipporag
    
    def update_book(self,
                    book_id: str,
                    chapters: List[str],
                    force_index_from_scratch: bool = True,
                    force_openie_from_scratch: bool = False,
                    metadata: Optional[Dict[str, Any]] = None) -> HippoRAG:
        """
        Update an existing book by re-indexing it.
        
        Parameters:
            book_id: str
                Identifier of the book to update
            chapters: List[str]
                New list of chapter/document strings
            force_index_from_scratch: bool, default=True
                If True, rebuild index from scratch
            force_openie_from_scratch: bool, default=False
                If True, rebuild OpenIE results from scratch
            metadata: Dict[str, Any], optional
                Updated metadata for the book
        
        Returns:
            HippoRAG: The updated HippoRAG instance
        
        Raises:
            ValueError: If book_id doesn't exist
        """
        if book_id not in self.books:
            raise ValueError(f"Book '{book_id}' does not exist. Use add_book() first.")
        
        logger.info("Updating book '%s'...", book_id)
        
        # Remove old instance
        del self.books[book_id]
        if book_id in self.book_metadata:
            old_metadata = self.book_metadata[book_id]
        else:
            old_metadata = {}
        
        # Add with new data
        return self.add_book(
            book_id=book_id,
            chapters=chapters,
            force_index_from_scratch=force_index_from_scratch,
            force_openie_from_scratch=force_openie_from_scratch,
            metadata={**old_metadata, **(metadata or {})}
        )
    
    def remove_book(self, book_id: str, delete_files: bool = False):
        """
        Remove a book from the manager.
        
        Parameters:
            book_id: str
                Identifier of the book to remove
            delete_files: bool, default=False
                If True, also delete the book's index files from disk
        
        Raises:
            ValueError: If book_id doesn't exist
        """
        if book_id not in self.books:
            raise ValueError(f"Book '{book_id}' does not exist.")
        
        logger.info("Removing book '%s'...", book_id)
        
        # Delete files if requested
        if delete_files:
            book_dir = os.path.join(self.base_save_dir, book_id)
            if os.path.exists(book_dir):
                import shutil
                shutil.rmtree(book_dir)
                logger.info("Deleted book directory: %s", book_dir)
        
        # Remove from manager
        del self.books[book_id]
        if book_id in self.book_metadata:
            del self.book_metadata[book_id]
        
        logger.info("Removed book '%s'", book_id)
    
    def get_book(self, book_id: str) -> HippoRAG:
        """
        Get the HippoRAG instance for a specific book.
        
        Parameters:
            book_id: str
                Identifier of the book
        
        Returns:
            HippoRAG: The HippoRAG instance for this book
        
        Raises:
            ValueError: If book_id doesn't exist
        """
        if book_id not in self.books:
            raise ValueError(f"Book '{book_id}' does not exist. Available books: {list(self.books.keys())}")
        return self.books[book_id]
    
    def query_single_book(self, 
                         book_id: str, 
                         query: str,
                         **kwargs) -> Tuple[List[QuerySolution], Any, Any]:
        """
        Query a single book.
        
        Parameters:
            book_id: str
                Identifier of the book to query
            query: str
                Query string
            **kwargs: Additional arguments to pass to rag_qa()
        
        Returns:
            Tuple containing:
            - List[QuerySolution]: Query solutions
            - Any: Response messages
            - Any: Metadata
        
        Raises:
            ValueError: If book_id doesn't exist
        """
        if book_id not in self.books:
            raise ValueError(f"Book '{book_id}' does not exist. Available books: {list(self.books.keys())}")
        
        logger.info("Querying book '%s': %s", book_id, query)
        return self.books[book_id].rag_qa(queries=[query], **kwargs)
    
    def query(self, 
              query: str, 
              book_ids: Optional[List[str]] = None,
              merge_results: bool = True,
              **kwargs) -> List[Dict[str, Any]]:
        """
        Query one or more books.
        
        Parameters:
            query: str
                Query string
            book_ids: List[str], optional
                List of book identifiers to query. If None, queries all books.
            merge_results: bool, default=True
                If True, merges results from all books into a single list with book_id metadata.
                If False, returns a dictionary mapping book_id to results.
            **kwargs: Additional arguments to pass to rag_qa()
        
        Returns:
            If merge_results=True:
                List[Dict]: List of results with book_id metadata, sorted by relevance
            If merge_results=False:
                Dict[str, Tuple]: Dictionary mapping book_id to (solutions, messages, metadata)
        
        Raises:
            ValueError: If any book_id doesn't exist
        """
        if book_ids is None:
            book_ids = list(self.books.keys())
        
        if not book_ids:
            logger.warning("No books to query")
            return [] if merge_results else {}
        
        # Validate book_ids
        invalid_ids = [bid for bid in book_ids if bid not in self.books]
        if invalid_ids:
            raise ValueError(f"Invalid book_ids: {invalid_ids}. Available books: {list(self.books.keys())}")
        
        logger.info("Querying %d book(s): %s", len(book_ids), query)
        
        all_results = []
        book_results = {}
        
        for book_id in book_ids:
            try:
                solutions, messages, metadata = self.books[book_id].rag_qa(
                    queries=[query], 
                    **kwargs
                )
                
                # Add book_id to each solution
                for solution in solutions:
                    if not hasattr(solution, 'metadata'):
                        solution.metadata = {}
                    solution.metadata['book_id'] = book_id
                
                if merge_results:
                    all_results.extend(solutions)
                else:
                    book_results[book_id] = (solutions, messages, metadata)
            
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error("Error querying book '%s': %s", book_id, e)
                if not merge_results:
                    book_results[book_id] = ([], None, None)
        
        if merge_results:
            # Sort by doc_scores if available (highest first)
            all_results.sort(
                key=lambda s: max(s.doc_scores) if s.doc_scores is not None and len(s.doc_scores) > 0 else 0,
                reverse=True
            )
            return all_results
        else:
            return book_results
    
    def list_books(self) -> List[Dict[str, Any]]:
        """
        List all books with their metadata.
        
        Returns:
            List[Dict]: List of book information dictionaries
        """
        books_info = []
        for book_id, metadata in self.book_metadata.items():
            book_info = {
                'book_id': book_id,
                'save_dir': os.path.join(self.base_save_dir, book_id),
                'has_index': book_id in self.books,
                **metadata
            }
            books_info.append(book_info)
        return books_info
    
    def get_book_info(self, book_id: str) -> Dict[str, Any]:
        """
        Get information about a specific book.
        
        Parameters:
            book_id: str
                Identifier of the book
        
        Returns:
            Dict: Book information including metadata
        
        Raises:
            ValueError: If book_id doesn't exist
        """
        if book_id not in self.books:
            raise ValueError(f"Book '{book_id}' does not exist. Available books: {list(self.books.keys())}")
        
        info = {
            'book_id': book_id,
            'save_dir': os.path.join(self.base_save_dir, book_id),
            'has_index': True,
            **self.book_metadata.get(book_id, {})
        }
        
        # Add graph info if available
        if hasattr(self.books[book_id], 'graph'):
            graph = self.books[book_id].graph
            info['graph_nodes'] = graph.vcount() if hasattr(graph, 'vcount') else 0
            info['graph_edges'] = graph.ecount() if hasattr(graph, 'ecount') else 0
        
        return info
    
    def load_existing_book(self, book_id: str) -> HippoRAG:
        """
        Load an existing book that was previously indexed.
        
        This is useful when you want to load a book that was indexed earlier
        without re-indexing it.
        
        Parameters:
            book_id: str
                Identifier of the book to load
        
        Returns:
            HippoRAG: The loaded HippoRAG instance
        
        Raises:
            ValueError: If book directory doesn't exist
        """
        book_dir = os.path.join(self.base_save_dir, book_id)
        if not os.path.exists(book_dir):
            raise ValueError(f"Book directory does not exist: {book_dir}")
        
        if book_id in self.books:
            logger.info("Book '%s' already loaded", book_id)
            return self.books[book_id]
        
        logger.info("Loading existing book '%s' from %s", book_id, book_dir)
        
        # Create config pointing to existing book directory
        book_config = BaseConfig(**asdict(self.base_config))
        book_config.save_dir = book_dir
        book_config.force_index_from_scratch = False
        book_config.force_openie_from_scratch = False
        
        # Apply pgvector overrides if provided
        if self.pgvector_overrides['host'] is not None:
            book_config.pgvector_host = self.pgvector_overrides['host']
        if self.pgvector_overrides['port'] is not None:
            book_config.pgvector_port = self.pgvector_overrides['port']
        if self.pgvector_overrides['database'] is not None:
            book_config.pgvector_database = self.pgvector_overrides['database']
        if self.pgvector_overrides['user'] is not None:
            book_config.pgvector_user = self.pgvector_overrides['user']
        if self.pgvector_overrides['password'] is not None:
            book_config.pgvector_password = self.pgvector_overrides['password']
        if self.pgvector_overrides['index_type'] is not None:
            book_config.pgvector_index_type = self.pgvector_overrides['index_type']
        if self.pgvector_overrides['index_lists'] is not None:
            book_config.pgvector_index_lists = self.pgvector_overrides['index_lists']
        
        # Apply Nebula Graph overrides if provided
        if self.nebula_overrides['host'] is not None:
            book_config.nebula_host = self.nebula_overrides['host']
        if self.nebula_overrides['port'] is not None:
            book_config.nebula_port = self.nebula_overrides['port']
        if self.nebula_overrides['user'] is not None:
            book_config.nebula_user = self.nebula_overrides['user']
        if self.nebula_overrides['password'] is not None:
            book_config.nebula_password = self.nebula_overrides['password']
        if self.nebula_overrides['space_name'] is not None:
            # For multi-book, use book_id as suffix to space name for isolation
            base_space = self.nebula_overrides['space_name']
            book_config.nebula_space_name = f"{base_space}_{book_id}"
        
        # Load the HippoRAG instance
        hipporag = HippoRAG(global_config=book_config)
        
        # Store the instance
        self.books[book_id] = hipporag
        
        # Try to load metadata if available
        metadata_file = os.path.join(book_dir, 'book_metadata.json')
        if os.path.exists(metadata_file):
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                self.book_metadata[book_id] = json.load(f)
        else:
            self.book_metadata[book_id] = {}
        
        logger.info("Successfully loaded book '%s'", book_id)
        return hipporag

