import logging
from typing import List, Dict, Callable, Optional
from ..utils.config_utils import BaseConfig
from ..embedding_store import EmbeddingStore
from ..information_extraction import OpenIE
from ..information_extraction.openie_manager import OpenIEManager
from ..graph.graph_builder import GraphBuilder
from ..graph.graph_manager import GraphManager
from ..utils.misc_utils import (
    reformat_openie_results,
    text_processing,
    extract_entity_nodes,
    flatten_facts
)

logger = logging.getLogger(__name__)


class Indexer:
    """
    Handles document indexing and deletion operations.
    """
    
    def __init__(self,
                 global_config: BaseConfig,
                 chunk_embedding_store: EmbeddingStore,
                 entity_embedding_store: EmbeddingStore,
                 fact_embedding_store: EmbeddingStore,
                 openie: OpenIE,
                 openie_manager: OpenIEManager,
                 graph,
                 graph_builder: GraphBuilder,
                 graph_manager: GraphManager,
                 node_to_node_stats: Dict,
                 ent_node_to_chunk_ids: Dict):
        """
        Initialize Indexer.
        
        Args:
            global_config: Global configuration
            chunk_embedding_store: Chunk embedding store
            entity_embedding_store: Entity embedding store
            fact_embedding_store: Fact embedding store
            openie: OpenIE instance
            openie_manager: OpenIEManager instance
            graph: The igraph graph object
            graph_builder: GraphBuilder instance
            graph_manager: GraphManager instance
            node_to_node_stats: Dictionary to store node-to-node statistics (will be modified)
            ent_node_to_chunk_ids: Dictionary mapping entity nodes to chunk IDs (will be modified)
        """
        self.global_config = global_config
        self.chunk_embedding_store = chunk_embedding_store
        self.entity_embedding_store = entity_embedding_store
        self.fact_embedding_store = fact_embedding_store
        self.openie = openie
        self.openie_manager = openie_manager
        self.graph = graph
        self.graph_builder = graph_builder
        self.graph_manager = graph_manager
        self.node_to_node_stats = node_to_node_stats
        self.ent_node_to_chunk_ids = ent_node_to_chunk_ids
    
    def index(self, docs: List[str], progress_callback: Optional[Callable[[str, int, int], None]] = None):
        """
        Indexes the given documents based on the HippoRAG 2 framework which generates an OpenIE knowledge graph
        based on the given documents and encodes passages, entities and facts separately for later retrieval.

        Parameters:
            docs : List[str]
                A list of documents to be indexed.
            progress_callback : Optional[Callable[[stage: str, current: int, total: int], None]]
                Optional callback invoked at each stage with (stage_name, current_step, total_steps).
        """
        total_docs = len(docs)
        logger.info("Indexing Documents")

        if progress_callback:
            progress_callback("embedding_chunks", 1, 6)

        logger.info("Performing OpenIE")

        self.chunk_embedding_store.insert_strings(docs)
        chunk_to_rows = self.chunk_embedding_store.get_all_id_to_rows()

        all_openie_info, chunk_keys_to_process = self.openie_manager.load_existing_openie(list(chunk_to_rows.keys()))
        new_openie_rows = {k: chunk_to_rows[k] for k in chunk_keys_to_process}

        if len(chunk_keys_to_process) > 0:
            new_ner_results_dict, new_triple_results_dict = self.openie.batch_openie(new_openie_rows)
            self.openie_manager.merge_openie_results(all_openie_info, new_openie_rows, new_ner_results_dict, new_triple_results_dict)

        if self.global_config.save_openie:
            self.openie_manager.save_openie_results(all_openie_info)

        if progress_callback:
            progress_callback("openie", 2, 6)

        ner_results_dict, triple_results_dict = reformat_openie_results(all_openie_info)

        # Filter to only include chunks that exist in chunk_to_rows
        # This handles cases where OpenIE results exist for chunks that are no longer in the database
        chunk_ids_in_store = set(chunk_to_rows.keys())
        ner_results_dict = {k: v for k, v in ner_results_dict.items() if k in chunk_ids_in_store}
        triple_results_dict = {k: v for k, v in triple_results_dict.items() if k in chunk_ids_in_store}

        assert len(chunk_to_rows) == len(ner_results_dict) == len(triple_results_dict), \
            f"len(chunk_to_rows): {len(chunk_to_rows)}, len(ner_results_dict): {len(ner_results_dict)}, len(triple_results_dict): {len(triple_results_dict)}"

        # prepare data_store
        chunk_ids = list(chunk_to_rows.keys())

        chunk_triples = [[text_processing(t) for t in triple_results_dict[chunk_id].triples] for chunk_id in chunk_ids]
        entity_nodes, chunk_triple_entities = extract_entity_nodes(chunk_triples)
        facts = flatten_facts(chunk_triples)

        if progress_callback:
            progress_callback("embedding_entities", 3, 6)

        logger.info("Encoding Entities")
        self.entity_embedding_store.insert_strings(entity_nodes)

        if progress_callback:
            progress_callback("embedding_facts", 4, 6)

        logger.info("Encoding Facts")
        self.fact_embedding_store.insert_strings([str(fact) for fact in facts])

        if progress_callback:
            progress_callback("graph_construction", 5, 6)

        logger.info("Constructing Graph")

        self.node_to_node_stats.clear()
        self.ent_node_to_chunk_ids.clear()

        self.graph_builder.add_fact_edges(chunk_ids, chunk_triples, self.ent_node_to_chunk_ids)
        num_new_chunks = self.graph_builder.add_passage_edges(chunk_ids, chunk_triple_entities)

        if num_new_chunks > 0:
            logger.info(f"Found {num_new_chunks} new chunks to save into graph.")
            self.graph_builder.add_synonymy_edges(self.entity_embedding_store, self.global_config)

            self.graph_manager.augment_graph(self.graph_builder)
            self.graph_manager.save_graph()

        if progress_callback:
            progress_callback("completed", 6, 6)
    
    def delete(self, 
               docs_to_delete: List[str],
               ready_to_retrieve: bool,
               prepare_retrieval_objects_func,
               proc_triples_to_docs: Dict):
        """
        Deletes the given documents from all data structures within the HippoRAG class.
        Note that triples and entities which are indexed from chunks that are not being removed will not be removed.

        Parameters:
            docs_to_delete : List[str]
                A list of documents to be deleted.
            ready_to_retrieve: Whether retrieval objects are ready
            prepare_retrieval_objects_func: Function to prepare retrieval objects if needed
            proc_triples_to_docs: Dictionary mapping processed triples to document IDs
        """
        # Making sure that all the necessary structures have been built.
        if not ready_to_retrieve:
            prepare_retrieval_objects_func()

        current_docs = set(self.chunk_embedding_store.get_all_texts())
        docs_to_delete = [doc for doc in docs_to_delete if doc in current_docs]

        # Get ids for chunks to delete
        chunk_ids_to_delete = set(
            [self.chunk_embedding_store.text_to_hash_id[chunk] for chunk in docs_to_delete])

        # Find triples in chunks to delete
        all_openie_info, _ = self.openie_manager.load_existing_openie([])
        triples_to_delete = []

        all_openie_info_with_deletes = []

        for openie_doc in all_openie_info:
            if openie_doc['idx'] in chunk_ids_to_delete:
                triples_to_delete.append(openie_doc['extracted_triples'])
            else:
                all_openie_info_with_deletes.append(openie_doc)

        triples_to_delete = flatten_facts(triples_to_delete)

        # Filter out triples that appear in unaltered chunks
        true_triples_to_delete = []

        for triple in triples_to_delete:
            proc_triple = tuple(text_processing(list(triple)))

            doc_ids = proc_triples_to_docs.get(str(proc_triple), set())

            non_deleted_docs = doc_ids.difference(chunk_ids_to_delete)

            if len(non_deleted_docs) == 0:
                true_triples_to_delete.append(triple)

        processed_true_triples_to_delete = [[text_processing(list(triple)) for triple in true_triples_to_delete]]
        entities_to_delete, _ = extract_entity_nodes(processed_true_triples_to_delete)
        processed_true_triples_to_delete = flatten_facts(processed_true_triples_to_delete)

        triple_ids_to_delete = set([self.fact_embedding_store.text_to_hash_id[str(triple)] for triple in processed_true_triples_to_delete])

        # Filter out entities that appear in unaltered chunks
        ent_ids_to_delete = [self.entity_embedding_store.text_to_hash_id[ent] for ent in entities_to_delete]

        filtered_ent_ids_to_delete = []

        for ent_node in ent_ids_to_delete:
            doc_ids = self.ent_node_to_chunk_ids.get(ent_node, set())

            non_deleted_docs = doc_ids.difference(chunk_ids_to_delete)

            if len(non_deleted_docs) == 0:
                filtered_ent_ids_to_delete.append(ent_node)

        logger.info(f"Deleting {len(chunk_ids_to_delete)} Chunks")
        logger.info(f"Deleting {len(triple_ids_to_delete)} Triples")
        logger.info(f"Deleting {len(filtered_ent_ids_to_delete)} Entities")

        self.openie_manager.save_openie_results(all_openie_info_with_deletes)

        self.entity_embedding_store.delete(filtered_ent_ids_to_delete)
        self.fact_embedding_store.delete(triple_ids_to_delete)
        self.chunk_embedding_store.delete(chunk_ids_to_delete)

        # Delete Nodes from Graph
        self.graph.delete_vertices(list(filtered_ent_ids_to_delete) + list(chunk_ids_to_delete))
        self.graph_manager.save_graph()

