import numpy as np
from typing import List, Dict, Optional, Tuple, Set
import logging
import psycopg2
from psycopg2.extras import execute_values
import ast

from .utils.misc_utils import compute_mdhash_id
from .database import init_embedding_table_with_conn, _create_vector_index_with_conn

logger = logging.getLogger(__name__)


class PgVectorEmbeddingStore:
    """
    EmbeddingStore implementation using pgvector for storage and retrieval.
    Provides the same interface as EmbeddingStore but uses PostgreSQL with pgvector extension.

    Note: 表初始化由 database.py 统一管理。
    """

    def __init__(self, embedding_model, db_config: Dict, batch_size: int, namespace: str,
                 index_type: str = "ivfflat", index_lists: int = 100, force_index_from_scratch: bool = False,
                 book_id: str = None):
        """
        Parameters:
            embedding_model: The embedding model
            db_config: PostgreSQL connection config dict with keys:
                - host: PostgreSQL host
                - port: PostgreSQL port
                - database: Database name
                - user: Username
                - password: Password
            batch_size: Batch size for processing (kept for compatibility)
            namespace: Namespace identifier (chunk, entity, fact)
            index_type: Type of vector index ('ivfflat' or 'hnsw')
            index_lists: Number of lists for IVFFlat index (only used when index_type='ivfflat')
            book_id: Optional book identifier for multi-tenancy data isolation
        """
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        self.namespace = namespace
        self.index_type = index_type
        self.index_lists = index_lists
        self.force_index_from_scratch = force_index_from_scratch
        self.book_id = book_id
        self.table_name = f"embeddings_{namespace}"
        
        # Get embedding dimension
        # First, try to get actual embedding dimension by encoding a test string
        # This is the most reliable method and must happen BEFORE connecting to database
        actual_dim_from_test = None
        try:
            test_embedding = embedding_model.batch_encode(["test"])
            if isinstance(test_embedding, np.ndarray):
                if test_embedding.ndim > 1:
                    actual_dim_from_test = test_embedding.shape[-1]
                elif test_embedding.ndim == 1:
                    actual_dim_from_test = test_embedding.shape[0]
                else:
                    actual_dim_from_test = len(test_embedding) if hasattr(test_embedding, '__len__') else 1
        except Exception as e:
            logger.debug(f"Could not determine actual embedding dimension from test encoding: {e}")
        
        # Set embedding dimension (prefer actual test result, then model attribute, then model name inference)
        if actual_dim_from_test is not None:
            self.embedding_dim = actual_dim_from_test
            logger.info(f"Determined embedding dimension {self.embedding_dim} from test encoding")
        elif hasattr(embedding_model, 'embedding_dim') and embedding_model.embedding_dim:
            self.embedding_dim = embedding_model.embedding_dim
            logger.info(f"Using embedding dimension {self.embedding_dim} from model attribute")
        else:
            # Try to infer from model name
            model_name = getattr(embedding_model, 'embedding_model_name', '')
            if 'text-embedding-3-large' in model_name:
                self.embedding_dim = 3072
            elif 'text-embedding-3-small' in model_name:
                self.embedding_dim = 1536
            elif 'text-embedding-ada-002' in model_name:
                self.embedding_dim = 1536
            elif 'text-embedding-v4' in model_name or 'text-embedding-4' in model_name:
                self.embedding_dim = 1024
            else:
                # Default to 1024 (common for many embedding models)
                logger.warning(f"Could not determine embedding_dim from model '{model_name}', defaulting to 1024")
                self.embedding_dim = 1024
            logger.info(f"Inferred embedding dimension {self.embedding_dim} from model name: {model_name}")
        
        # If we got actual dimension from test but it differs from inferred, use actual
        if actual_dim_from_test is not None and actual_dim_from_test != self.embedding_dim:
            logger.info(f"Using actual embedding dimension {actual_dim_from_test} (differs from inferred {self.embedding_dim})")
            self.embedding_dim = actual_dim_from_test
        
        # Connect to PostgreSQL
        try:
            self.conn = psycopg2.connect(**db_config)
            self.conn.autocommit = False
            
            # Drop table if force_index_from_scratch
            if force_index_from_scratch:
                with self.conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {self.table_name} CASCADE;")
                    self.conn.commit()
                    logger.info(f"Dropped existing table {self.table_name} (force_index_from_scratch=True)")
            
            self._init_table()
            logger.info(f"Connected to PostgreSQL and initialized table {self.table_name} with dimension {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def _init_table(self):
        """Initialize the table using unified database module."""
        # 使用统一的数据库模块初始化表
        init_embedding_table_with_conn(
            self.conn,
            self.table_name,
            self.embedding_dim,
            self.index_type,
            self.index_lists
        )
        logger.info(f"Table {self.table_name} initialized via database module")
    
    def _update_table_dimension(self, new_dim: int):
        """Update table to use new embedding dimension. Only works if table is empty."""
        with self.conn.cursor() as cur:
            # Check if table has data
            cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cur.fetchone()[0]
            
            if count > 0:
                raise ValueError(
                    f"Cannot update table dimension from {self.embedding_dim} to {new_dim}: "
                    f"table {self.table_name} already contains {count} records. "
                    f"Please drop the table manually or use force_index_from_scratch=True."
                )
            
            # Drop and recreate table with new dimension
            logger.info(f"Recreating table {self.table_name} with dimension {new_dim}")
            cur.execute(f"DROP TABLE IF EXISTS {self.table_name} CASCADE;")
            self.conn.commit()
            
            # Recreate table with new dimension
            cur.execute(f"""
                CREATE TABLE {self.table_name} (
                    hash_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector({new_dim}),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()
            logger.info(f"Table {self.table_name} recreated with dimension {new_dim}")
    
    def _ensure_index(self):
        """Ensure index exists after data is inserted."""
        # 使用统一的数据库模块确保索引存在
        _create_vector_index_with_conn(
            self.conn,
            self.table_name,
            self.index_type,
            self.index_lists
        )
    
    def get_missing_string_hash_ids(self, texts: List[str]) -> Dict:
        """Get hash IDs that don't exist in the database."""
        nodes_dict = {}
        for text in texts:
            hash_id = compute_mdhash_id(text, prefix=self.namespace + "-")
            nodes_dict[hash_id] = {'content': text}
        
        if not nodes_dict:
            return {}
        
        # Check which hash_ids exist
        with self.conn.cursor() as cur:
            hash_ids = list(nodes_dict.keys())
            if not hash_ids:
                return {}
            
            placeholders = ','.join(['%s'] * len(hash_ids))
            cur.execute(
                f"SELECT hash_id FROM {self.table_name} WHERE hash_id IN ({placeholders})",
                hash_ids
            )
            existing = {row[0] for row in cur.fetchall()}
        
        # Return only missing ones
        missing = {h: v for h, v in nodes_dict.items() if h not in existing}
        return missing
    
    def insert_strings(self, texts: List[str]):
        """Insert texts and their embeddings."""
        missing_dict = self.get_missing_string_hash_ids(texts)
        
        if not missing_dict:
            logger.info("All texts already exist in database")
            return {}
        
        missing_ids = list(missing_dict.keys())
        texts_to_encode = [missing_dict[h]['content'] for h in missing_ids]
        
        logger.info(f"Encoding {len(texts_to_encode)} new texts")
        embeddings = self.embedding_model.batch_encode(texts_to_encode)
        
        # Ensure embeddings are numpy arrays
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)
        
        # Check actual embedding dimension and update if needed
        if embeddings.size > 0:
            # Get actual dimension from first embedding
            if embeddings.ndim > 1:
                actual_dim = embeddings.shape[-1]
            elif len(embeddings) > 0:
                actual_dim = len(embeddings[0]) if hasattr(embeddings[0], '__len__') else 1
            else:
                actual_dim = embeddings.shape[0] if embeddings.ndim > 0 else 1
            
            if actual_dim != self.embedding_dim:
                # Check if table is empty
                with self.conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    count = cur.fetchone()[0]
                
                if count == 0:
                    # Table is empty, safe to update
                    logger.warning(f"Embedding dimension mismatch: table expects {self.embedding_dim}, but got {actual_dim}. Updating table structure...")
                    self._update_table_dimension(actual_dim)
                    self.embedding_dim = actual_dim
                else:
                    # Table has data, check if existing data matches
                    raise ValueError(
                        f"Embedding dimension mismatch: table {self.table_name} expects {self.embedding_dim} dimensions, "
                        f"but embedding model produces {actual_dim} dimensions. Table already contains {count} records. "
                        f"Please use force_index_from_scratch=True to rebuild."
                    )
        
        # Insert into database
        try:
            with self.conn.cursor() as cur:
                data = [
                    (hash_id, content, embedding.tolist(), self.book_id)
                    for hash_id, content, embedding in zip(missing_ids, texts_to_encode, embeddings)
                ]
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {self.table_name} (hash_id, content, embedding, book_id)
                    VALUES %s
                    ON CONFLICT (hash_id) DO NOTHING
                    """,
                    data
                )
                self.conn.commit()

            # Ensure index exists after insert
            self._ensure_index()

            logger.info(f"Inserted {len(missing_ids)} records into {self.table_name}")
        except Exception as e:
            logger.error(f"Error inserting records: {e}")
            self.conn.rollback()
            raise
    
    def _parse_vector(self, vector_value) -> np.ndarray:
        """Parse pgvector vector value to numpy array."""
        if isinstance(vector_value, np.ndarray):
            return vector_value
        elif isinstance(vector_value, (list, tuple)):
            return np.array(vector_value, dtype=np.float32)
        elif isinstance(vector_value, str):
            # pgvector returns vector as string like '[0.1,0.2,0.3]'
            try:
                # Try to parse as Python literal
                parsed = ast.literal_eval(vector_value)
                return np.array(parsed, dtype=np.float32)
            except (ValueError, SyntaxError):
                # If that fails, try to parse manually
                # Remove brackets and split by comma
                cleaned = vector_value.strip('[]')
                values = [float(x.strip()) for x in cleaned.split(',')]
                return np.array(values, dtype=np.float32)
        else:
            # Try direct conversion
            return np.array(vector_value, dtype=np.float32)
    
    def get_embedding(self, hash_id: str, dtype=np.float32) -> np.ndarray:
        """Get a single embedding by hash_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT embedding FROM {self.table_name} WHERE hash_id = %s",
                (hash_id,)
            )
            result = cur.fetchone()
            if result:
                vector = self._parse_vector(result[0])
                return vector.astype(dtype) if dtype != np.float32 else vector
            return None
    
    def get_embeddings(self, hash_ids: List[str], dtype=np.float32) -> List[np.ndarray]:
        """Get multiple embeddings by hash_ids."""
        if not hash_ids:
            return []
        
        with self.conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(hash_ids))
            cur.execute(
                f"SELECT hash_id, embedding FROM {self.table_name} WHERE hash_id IN ({placeholders})",
                hash_ids
            )
            results = {}
            for row in cur.fetchall():
                vector = self._parse_vector(row[1])
                if dtype != np.float32:
                    vector = vector.astype(dtype)
                results[row[0]] = vector
        
        # Return in the same order as hash_ids, None for missing ones
        return [results.get(hid) for hid in hash_ids]
    
    def similarity_search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[str, str, float]]:
        """
        Perform similarity search using pgvector.

        Parameters:
            query_embedding: Query embedding vector
            top_k: Number of top results to return

        Returns:
            List of (hash_id, content, similarity_score) tuples, sorted by similarity descending
        """
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.array(query_embedding)

        # Ensure 1D array
        if query_embedding.ndim > 1:
            query_embedding = query_embedding.flatten()

        with self.conn.cursor() as cur:
            # Use cosine distance (<=>) and convert to similarity (1 - distance)
            # pgvector's <=> operator returns cosine distance (0 = identical, 2 = opposite)
            if self.book_id:
                # Filter by book_id for multi-tenancy
                cur.execute(f"""
                    SELECT hash_id, content, 1 - (embedding <=> %s::vector) as similarity
                    FROM {self.table_name}
                    WHERE book_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding.tolist(), self.book_id, query_embedding.tolist(), top_k))
            else:
                cur.execute(f"""
                    SELECT hash_id, content, 1 - (embedding <=> %s::vector) as similarity
                    FROM {self.table_name}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding.tolist(), query_embedding.tolist(), top_k))

            results = cur.fetchall()
            return [(row[0], row[1], float(row[2])) for row in results]
    
    def get_row(self, hash_id: str) -> Dict:
        """Get a row by hash_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT hash_id, content FROM {self.table_name} WHERE hash_id = %s",
                (hash_id,)
            )
            row = cur.fetchone()
            if row:
                return {'hash_id': row[0], 'content': row[1]}
            return None
    
    def get_rows(self, hash_ids: List[str], dtype=np.float32) -> Dict:
        """Get multiple rows by hash_ids."""
        if not hash_ids:
            return {}
        
        with self.conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(hash_ids))
            cur.execute(
                f"SELECT hash_id, content FROM {self.table_name} WHERE hash_id IN ({placeholders})",
                hash_ids
            )
            results = {row[0]: {'hash_id': row[0], 'content': row[1]} for row in cur.fetchall()}
            return results
    
    def get_all_ids(self) -> List[str]:
        """Get all hash_ids."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT hash_id FROM {self.table_name}")
            return [row[0] for row in cur.fetchall()]
    
    def get_all_id_to_rows(self) -> Dict:
        """Get all hash_ids mapped to their rows."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT hash_id, content FROM {self.table_name}")
            results = {row[0]: {'hash_id': row[0], 'content': row[1]} for row in cur.fetchall()}
            return results
    
    def get_all_texts(self) -> Set[str]:
        """Get all unique text contents."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT content FROM {self.table_name}")
            return {row[0] for row in cur.fetchall()}
    
    def get_hash_id(self, text: str) -> Optional[str]:
        """Get hash_id for a given text."""
        hash_id = compute_mdhash_id(text, prefix=self.namespace + "-")
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT hash_id FROM {self.table_name} WHERE hash_id = %s",
                (hash_id,)
            )
            result = cur.fetchone()
            if result:
                return result[0]
            return None
    
    def delete(self, hash_ids: List[str]):
        """Delete records by hash_ids."""
        if not hash_ids:
            return

        try:
            with self.conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(hash_ids))
                cur.execute(
                    f"DELETE FROM {self.table_name} WHERE hash_id IN ({placeholders})",
                    hash_ids
                )
                deleted_count = cur.rowcount
                self.conn.commit()
                logger.info(f"Deleted {deleted_count} records from {self.table_name}")
        except Exception as e:
            logger.error(f"Error deleting records: {e}")
            self.conn.rollback()
            raise

    def delete_by_book(self, book_id: str):
        """Delete all records for a specific book."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.table_name} WHERE book_id = %s",
                    (book_id,)
                )
                deleted_count = cur.rowcount
                self.conn.commit()
                logger.info(f"Deleted {deleted_count} records for book {book_id} from {self.table_name}")
                return deleted_count
        except Exception as e:
            logger.error(f"Error deleting records for book {book_id}: {e}")
            self.conn.rollback()
            raise
    
    def close(self):
        """Close database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info(f"Closed connection to PostgreSQL for {self.table_name}")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()

