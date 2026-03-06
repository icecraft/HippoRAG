"""
Simplified HippoRAG main class.

This is a refactored version that delegates to specialized components:
- Indexer: Document indexing
- Retriever: Graph-based retrieval
- QAEngine: Question answering
- GraphManager: Graph operations

The class acts as a facade coordinating these components.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple

from .utils.config_utils import BaseConfig
from .utils.misc_utils import QuerySolution
from .llm import _get_llm_class, BaseLLM
from .embedding_model import _get_embedding_model_class, BaseEmbeddingModel
from .embedding_store import create_embedding_store
from .information_extraction.openie_manager import OpenIEManager
from .graph import create_graph_manager
from .indexing import Indexer
from .retrieval import Retriever
from .qa import QAEngine
from .retrieval_helper import RetrievalHelper
from .qa_helper import QAHelper

logger = logging.getLogger(__name__)


class HippoRAG:
    """
    Simplified HippoRAG facade class.

    Coordinates indexing, retrieval, and QA operations.
    """

    def __init__(
        self,
        global_config: Optional[BaseConfig] = None,
        save_dir: Optional[str] = None,
        llm_model_name: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        embedding_model_name: Optional[str] = None,
        embedding_base_url: Optional[str] = None
    ):
        """
        Initialize HippoRAG.

        Parameters:
            global_config: Configuration object
            save_dir: Directory for saving data
            llm_model_name: LLM model name
            llm_base_url: LLM API base URL
            embedding_model_name: Embedding model name
            embedding_base_url: Embedding API base URL
        """
        # Initialize configuration
        self._init_config(
            global_config, save_dir, llm_model_name, llm_base_url,
            embedding_model_name, embedding_base_url
        )

        # Initialize components
        self._init_llm()
        self._init_embedding_model()
        self._init_embedding_stores()
        self._init_openie()
        self._init_graph()
        self._init_components()
        self._init_helpers()

        logger.info(f"HippoRAG initialized with save_dir={self.config.save_dir}")

    def _init_config(
        self,
        global_config: Optional[BaseConfig],
        save_dir: Optional[str],
        llm_model_name: Optional[str],
        llm_base_url: Optional[str],
        embedding_model_name: Optional[str],
        embedding_base_url: Optional[str]
    ):
        """Initialize configuration."""
        if global_config is not None:
            self.config = global_config
        else:
            # Build config from parameters
            config_kwargs = {}
            if save_dir:
                config_kwargs['save_dir'] = save_dir
            if llm_model_name:
                config_kwargs['llm_name'] = llm_model_name
            if llm_base_url:
                config_kwargs['llm_base_url'] = llm_base_url
            if embedding_model_name:
                config_kwargs['embedding_model_name'] = embedding_model_name
            if embedding_base_url:
                config_kwargs['embedding_base_url'] = embedding_base_url

            self.config = BaseConfig(**config_kwargs)

    def _init_llm(self):
        """Initialize LLM."""
        llm_class = _get_llm_class()
        self.llm = llm_class.from_experiment_config(self.config)
        logger.debug(f"LLM initialized: {self.config.llm_name}")

    def _init_embedding_model(self):
        """Initialize embedding model."""
        embedding_class = _get_embedding_model_class()
        self.embedding_model = embedding_class(
            global_config=self.config,
            embedding_model_name=self.config.embedding_model_name
        )
        logger.debug(f"Embedding model initialized: {self.config.embedding_model_name}")

    def _init_embedding_stores(self):
        """Initialize embedding stores."""
        self.chunk_embedding_store = create_embedding_store(
            self.embedding_model, self.config, "chunk"
        )
        self.entity_embedding_store = create_embedding_store(
            self.embedding_model, self.config, "entity"
        )
        self.fact_embedding_store = create_embedding_store(
            self.embedding_model, self.config, "fact"
        )
        logger.debug("Embedding stores initialized")

    def _init_openie(self):
        """Initialize OpenIE manager."""
        self.openie = OpenIEManager(
            self.llm,
            save_dir=self.config.save_dir,
            force_reindex=self.config.force_openie_from_scratch
        )
        logger.debug("OpenIE manager initialized")

    def _init_graph(self):
        """Initialize graph manager."""
        self.graph_manager = create_graph_manager(self.config)
        logger.debug("Graph manager initialized")

    def _init_components(self):
        """Initialize main components."""
        # Indexer
        self.indexer = Indexer(
            llm=self.llm,
            embedding_model=self.embedding_model,
            chunk_embedding_store=self.chunk_embedding_store,
            entity_embedding_store=self.entity_embedding_store,
            fact_embedding_store=self.fact_embedding_store,
            openie=self.openie,
            graph_manager=self.graph_manager,
            config=self.config
        )

        # Retriever
        self.retriever = Retriever(
            llm=self.llm,
            embedding_model=self.embedding_model,
            chunk_embedding_store=self.chunk_embedding_store,
            entity_embedding_store=self.entity_embedding_store,
            fact_embedding_store=self.fact_embedding_store,
            graph_manager=self.graph_manager,
            config=self.config
        )

        # QA Engine
        self.qa_engine = QAEngine(
            llm=self.llm,
            config=self.config
        )

        logger.debug("Main components initialized")

    def _init_helpers(self):
        """Initialize helper classes."""
        self.retrieval_helper = RetrievalHelper(
            self.config,
            self.embedding_model,
            self.chunk_embedding_store,
            self.entity_embedding_store,
            self.fact_embedding_store
        )

        self.qa_helper = QAHelper(
            self.config,
            self.llm
        )

    # ==================== Public API ====================

    def index(self, docs: List[str]) -> Dict:
        """
        Index documents.

        Parameters:
            docs: List of documents to index

        Returns:
            Dict with indexing results
        """
        logger.info(f"Indexing {len(docs)} documents")
        return self.indexer.index(docs)

    def delete(self, docs: List[str]) -> Dict:
        """
        Delete documents from index.

        Parameters:
            docs: List of documents to delete

        Returns:
            Dict with deletion results
        """
        logger.info(f"Deleting {len(docs)} documents")
        return self.indexer.delete(docs)

    def retrieve(
        self,
        queries: List[str],
        num_to_retrieve: Optional[int] = None,
        return_scores: bool = False,
        **kwargs
    ) -> Tuple[List[QuerySolution], Optional[Dict]]:
        """
        Retrieve passages for queries.

        Parameters:
            queries: List of queries
            num_to_retrieve: Number of passages to retrieve
            return_scores: Whether to return scores

        Returns:
            Tuple of (query_solutions, metrics)
        """
        logger.info(f"Retrieving for {len(queries)} queries")
        return self.retriever.retrieve(queries, num_to_retrieve, return_scores, **kwargs)

    def retrieve_dpr(
        self,
        queries: List[str],
        num_to_retrieve: Optional[int] = None,
        return_scores: bool = False,
        **kwargs
    ) -> Tuple[List[QuerySolution], Optional[Dict]]:
        """
        DPR-based retrieval.

        Parameters:
            queries: List of queries
            num_to_retrieve: Number of passages to retrieve
            return_scores: Whether to return scores

        Returns:
            Tuple of (query_solutions, metrics)
        """
        logger.info(f"DPR retrieving for {len(queries)} queries")
        return self.retriever.retrieve_dpr(queries, num_to_retrieve, return_scores, **kwargs)

    def rag_qa(
        self,
        queries: List[str],
        num_to_retrieve: Optional[int] = None,
        return_passages: bool = True,
        **kwargs
    ) -> Tuple[List[QuerySolution], List[str], Optional[Dict]]:
        """
        RAG-based QA.

        Parameters:
            queries: List of questions
            num_to_retrieve: Number of passages to retrieve
            return_passages: Whether to return passages

        Returns:
            Tuple of (query_solutions, answers, metrics)
        """
        logger.info(f"RAG QA for {len(queries)} queries")

        # Retrieve
        query_solutions, retrieve_metrics = self.retrieve(queries, num_to_retrieve, **kwargs)

        # Generate answers
        answers = []
        for i, qs in enumerate(query_solutions):
            passages = qs.docs if hasattr(qs, 'docs') else []
            answer, _ = self.qa_helper.generate_answer(queries[i], passages)
            answers.append(answer)

        return query_solutions, answers, retrieve_metrics

    def rag_qa_dpr(
        self,
        queries: List[str],
        num_to_retrieve: Optional[int] = None,
        return_passages: bool = True,
        **kwargs
    ) -> Tuple[List[QuerySolution], List[str], Optional[Dict]]:
        """
        DPR-based RAG QA.

        Parameters:
            queries: List of questions
            num_to_retrieve: Number of passages to retrieve
            return_passages: Whether to return passages

        Returns:
            Tuple of (query_solutions, answers, metrics)
        """
        logger.info(f"DPR RAG QA for {len(queries)} queries")

        # Retrieve
        query_solutions, retrieve_metrics = self.retrieve_dpr(queries, num_to_retrieve, **kwargs)

        # Generate answers
        answers = []
        for i, qs in enumerate(query_solutions):
            passages = qs.docs if hasattr(qs, 'docs') else []
            answer, _ = self.qa_helper.generate_answer(queries[i], passages)
            answers.append(answer)

        return query_solutions, answers, retrieve_metrics

    def qa(
        self,
        query: str,
        num_to_retrieve: Optional[int] = None
    ) -> str:
        """
        Simple QA interface.

        Parameters:
            query: Single question
            num_to_retrieve: Number of passages to retrieve

        Returns:
            Answer string
        """
        _, answers, _ = self.rag_qa([query], num_to_retrieve)
        return answers[0] if answers else ""

    # ==================== Delegation Methods ====================

    def add_fact_edges(self, triples, graph):
        """Add fact edges to graph (delegates to graph_manager)."""
        return self.graph_manager.add_fact_edges(triples, graph)

    def add_passage_edges(self, passages, graph):
        """Add passage edges to graph (delegates to graph_manager)."""
        return self.graph_manager.add_passage_edges(passages, graph)

    def add_synonymy_edges(self, graph):
        """Add synonymy edges to graph (delegates to graph_manager)."""
        return self.graph_manager.add_synonymy_edges(graph)

    def load_existing_openie(self, *args, **kwargs):
        """Load existing OpenIE results (delegates to openie)."""
        return self.openie.load_existing(*args, **kwargs)

    def save_openie_results(self, *args, **kwargs):
        """Save OpenIE results (delegates to openie)."""
        return self.openie.save(*args, **kwargs)

    def augment_graph(self, graph):
        """Augment graph (delegates to graph_manager)."""
        return self.graph_manager.augment(graph)

    def save_igraph(self, graph):
        """Save graph (delegates to graph_manager)."""
        return self.graph_manager.save(graph)

    def get_graph_info(self, graph):
        """Get graph info (delegates to graph_manager)."""
        return self.graph_manager.get_info(graph)
