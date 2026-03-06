"""
Retrieval helper functions for HippoRAG.

Contains internal retrieval logic extracted from HippoRAG class.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from tqdm import tqdm

from .utils.misc_utils import QuerySolution
from .utils.embed_utils import retrieve_knn

logger = logging.getLogger(__name__)


class RetrievalHelper:
    """
    Helper class for retrieval operations.

    Contains internal methods for:
    - Query embedding
    - Fact scoring
    - Dense passage retrieval
    - Weight calculation
    """

    def __init__(self, config, embedding_model, chunk_embedding_store, entity_embedding_store, fact_embedding_store):
        """
        Initialize retrieval helper.

        Parameters:
            config: BaseConfig instance
            embedding_model: Embedding model instance
            chunk_embedding_store: Chunk embedding store
            entity_embedding_store: Entity embedding store
            fact_embedding_store: Fact embedding store
        """
        self.config = config
        self.embedding_model = embedding_model
        self.chunk_embedding_store = chunk_embedding_store
        self.entity_embedding_store = entity_embedding_store
        self.fact_embedding_store = fact_embedding_store

    def get_query_embeddings(self, queries: List[str]) -> np.ndarray:
        """
        Get embeddings for queries.

        Parameters:
            queries: List of query strings

        Returns:
            Query embeddings as numpy array
        """
        query_embeddings = self.embedding_model.batch_encode(queries)
        return query_embeddings

    def get_fact_scores(
        self,
        queries: List[str],
        query_embeddings: np.ndarray,
        num_to_retrieve: int = 10
    ) -> Tuple[List[QuerySolution], List[List[Tuple[str, str, float]]]]:
        """
        Get fact scores for queries.

        Parameters:
            queries: List of query strings
            query_embeddings: Query embeddings
            num_to_retrieve: Number of facts to retrieve

        Returns:
            Tuple of (query_solutions, fact_results)
        """
        query_solutions = []
        fact_results = []

        for i, query in enumerate(queries):
            query_embedding = query_embeddings[i]

            # Retrieve facts
            fact_scores = self.fact_embedding_store.similarity_search(
                query_embedding, top_k=num_to_retrieve
            )

            # Create query solution
            docs = [fs[1] for fs in fact_scores]
            scores = np.array([fs[2] for fs in fact_scores])

            qs = QuerySolution(
                question=query,
                docs=docs,
                doc_scores=scores
            )
            query_solutions.append(qs)
            fact_results.append(fact_scores)

        return query_solutions, fact_results

    def dense_passage_retrieval(
        self,
        queries: List[str],
        query_embeddings: np.ndarray,
        num_to_retrieve: int = 10
    ) -> List[QuerySolution]:
        """
        Dense passage retrieval (DPR).

        Parameters:
            queries: List of query strings
            query_embeddings: Query embeddings
            num_to_retrieve: Number of passages to retrieve

        Returns:
            List of QuerySolution objects
        """
        query_solutions = []

        for i, query in enumerate(queries):
            query_embedding = query_embeddings[i]

            # Retrieve passages
            passage_scores = self.chunk_embedding_store.similarity_search(
                query_embedding, top_k=num_to_retrieve
            )

            docs = [ps[1] for ps in passage_scores]
            scores = np.array([ps[2] for ps in passage_scores])

            qs = QuerySolution(
                question=query,
                docs=docs,
                doc_scores=scores
            )
            query_solutions.append(qs)

        return query_solutions

    def get_top_k_weights(
        self,
        query_solution: QuerySolution,
        entity_id_to_idx: Dict[str, int],
        entity_embedding_store,
        linking_top_k: int = 5,
        retrieval_top_k: int = 200,
        synonymy_edge_topk: int = 2047
    ) -> np.ndarray:
        """
        Get top-k weights for Personalized PageRank.

        Parameters:
            query_solution: QuerySolution object
            entity_id_to_idx: Entity ID to index mapping
            entity_embedding_store: Entity embedding store
            linking_top_k: Top-k entities for linking
            retrieval_top_k: Top-k for retrieval
            synonymy_edge_topk: Top-k for synonymy edges

        Returns:
            Weight vector for PPR
        """
        n_entities = len(entity_id_to_idx)
        weights = np.zeros(n_entities)

        if not query_solution.docs:
            return weights

        # Get entity embeddings for docs
        doc_texts = query_solution.docs[:retrieval_top_k]
        doc_embeddings = self.entity_embedding_store.get_embeddings(doc_texts)

        if doc_embeddings is None or len(doc_embeddings) == 0:
            return weights

        # Calculate similarity scores
        query_embedding = self.embedding_model.encode([query_solution.question])[0]

        for doc_idx, doc_embedding in enumerate(doc_embeddings):
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )

            # Get entity IDs from docs
            doc_text = doc_texts[doc_idx] if doc_idx < len(doc_texts) else None
            if doc_text:
                # Simple hash-based entity ID
                entity_id = f"entity_{hash(doc_text) % 1000000}"
                if entity_id in entity_id_to_idx:
                    weights[entity_id_to_idx[entity_id]] += similarity

        # Normalize weights
        if weights.sum() > 0:
            weights = weights / weights.sum()

        return weights
