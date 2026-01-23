import numpy as np
from typing import List, Dict, Optional, Tuple, Set
import logging
from copy import deepcopy
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import sql

from .utils.misc_utils import compute_mdhash_id

logger = logging.getLogger(__name__)


class PgVectorEmbeddingStore:
    """
    EmbeddingStore implementation using pgvector for storage and retrieval.
    Provides the same interface as EmbeddingStore but uses PostgreSQL with pgvector extension.
    """
    
    def __init__(self, embedding_model, db_config: Dict, batch_size: int, namespace: str,
                 index_type: str = "ivfflat", index_lists: int = 100):
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
        """
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        self.namespace = namespace
        self.index_type = index_type
        self.index_lists = index_lists
        self.table_name = f"embeddings_{namespace}"
        
        # Get embedding dimension
        # Try to get from embedding_model, or infer from model name
        if hasattr(embedding_model, 'embedding_dim') and embedding_model.embedding_dim:
            self.embedding_dim = embedding_model.embedding_dim
        else:
            # Try to infer from model name
            model_name = getattr(embedding_model, 'embedding_model_name', '')
            if 'text-embedding-3-large' in model_name:
                self.embedding_dim = 3072
            elif 'text-embedding-3-small' in model_name:
                self.embedding_dim = 1536
            elif 'text-embedding-ada-002' in model_name:
                self.embedding_dim = 1536
            else:
                # Default to 1536 (most common)
                logger.warning(f"Could not determine embedding_dim from model '{model_name}', defaulting to 1536")
                self.embedding_dim = 1536
        
        # Connect to PostgreSQL
        try:
            self.conn = psycopg2.connect(**db_config)
            self.conn.autocommit = False
            self._init_table()
            logger.info(f"Connected to PostgreSQL and initialized table {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def _init_table(self):
        """Initialize the table with pgvector extension."""
        with self.conn.cursor() as cur:
            try:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.conn.commit()
            except Exception as e:
                logger.warning(f"Could not create vector extension (may already exist): {e}")
                self.conn.rollback()
            
            # Create table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    hash_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector({self.embedding_dim}),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()
            
            # Create index for similarity search
            index_name = f"{self.table_name}_embedding_idx"
            try:
                if self.index_type == "hnsw":
                    # HNSW index (faster but uses more memory)
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON {self.table_name}
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);
                    """)
                else:
                    # IVFFlat index (more memory-efficient)
                    # Note: IVFFlat requires some data to exist before creating index
                    # We'll create it after checking if table has data
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    count = cur.fetchone()[0]
                    if count > 0:
                        cur.execute(f"""
                            CREATE INDEX IF NOT EXISTS {index_name}
                            ON {self.table_name}
                            USING ivfflat (embedding vector_cosine_ops)
                            WITH (lists = {self.index_lists});
                        """)
                    else:
                        logger.info(f"Table {self.table_name} is empty, will create IVFFlat index after first insert")
                self.conn.commit()
            except Exception as e:
                logger.warning(f"Could not create index (may already exist or need data first): {e}")
                self.conn.rollback()
    
    def _ensure_index(self):
        """Ensure index exists after data is inserted."""
        if self.index_type == "ivfflat":
            index_name = f"{self.table_name}_embedding_idx"
            with self.conn.cursor() as cur:
                # Check if index exists
                cur.execute("""
                    SELECT COUNT(*) FROM pg_indexes 
                    WHERE indexname = %s
                """, (index_name,))
                if cur.fetchone()[0] == 0:
                    # Check if we have data
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    count = cur.fetchone()[0]
                    if count > 0:
                        try:
                            cur.execute(f"""
                                CREATE INDEX {index_name}
                                ON {self.table_name}
                                USING ivfflat (embedding vector_cosine_ops)
                                WITH (lists = {self.index_lists});
                            """)
                            self.conn.commit()
                            logger.info(f"Created IVFFlat index {index_name}")
                        except Exception as e:
                            logger.warning(f"Could not create index: {e}")
                            self.conn.rollback()
    
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
        
        # Insert into database
        try:
            with self.conn.cursor() as cur:
                data = [
                    (hash_id, content, embedding.tolist())
                    for hash_id, content, embedding in zip(missing_ids, texts_to_encode, embeddings)
                ]
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {self.table_name} (hash_id, content, embedding)
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
    
    def get_embedding(self, hash_id: str, dtype=np.float32) -> np.ndarray:
        """Get a single embedding by hash_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT embedding FROM {self.table_name} WHERE hash_id = %s",
                (hash_id,)
            )
            result = cur.fetchone()
            if result:
                return np.array(result[0], dtype=dtype)
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
            results = {row[0]: np.array(row[1], dtype=dtype) for row in cur.fetchall()}
        
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
    
    def close(self):
        """Close database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info(f"Closed connection to PostgreSQL for {self.table_name}")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()

