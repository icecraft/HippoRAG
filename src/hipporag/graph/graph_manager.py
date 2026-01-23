import os
import logging
from typing import Dict
import igraph as ig

from ..utils.config_utils import BaseConfig
from ..embedding_store import EmbeddingStore

logger = logging.getLogger(__name__)


class GraphManager:
    """
    Manages graph initialization, saving, and information retrieval.
    """
    
    def __init__(self, 
                 global_config: BaseConfig,
                 working_dir: str,
                 graph: ig.Graph,
                 entity_embedding_store: EmbeddingStore,
                 chunk_embedding_store: EmbeddingStore,
                 fact_embedding_store: EmbeddingStore,
                 node_to_node_stats: Dict):
        """
        Initialize GraphManager.
        
        Args:
            global_config: Global configuration
            working_dir: Working directory path
            graph: The igraph graph object
            entity_embedding_store: Entity embedding store
            chunk_embedding_store: Chunk embedding store
            fact_embedding_store: Fact embedding store
            node_to_node_stats: Dictionary mapping node pairs to statistics
        """
        self.global_config = global_config
        self.working_dir = working_dir
        self.graph = graph
        self.entity_embedding_store = entity_embedding_store
        self.chunk_embedding_store = chunk_embedding_store
        self.fact_embedding_store = fact_embedding_store
        self.node_to_node_stats = node_to_node_stats
        
        self._graph_pickle_filename = os.path.join(
            self.working_dir, f"graph.pickle"
        )
    
    def initialize_graph(self) -> ig.Graph:
        """
        Initializes a graph using a Pickle file if available or creates a new graph.

        The function attempts to load a pre-existing graph stored in a Pickle file. If the file
        is not present or the graph needs to be created from scratch, it initializes a new directed
        or undirected graph based on the global configuration. If the graph is loaded successfully
        from the file, pertinent information about the graph (number of nodes and edges) is logged.

        Returns:
            ig.Graph: A pre-loaded or newly initialized graph.
        """
        preloaded_graph = None

        if not self.global_config.force_index_from_scratch:
            if os.path.exists(self._graph_pickle_filename):
                preloaded_graph = ig.Graph.Read_Pickle(self._graph_pickle_filename)

        if preloaded_graph is None:
            return ig.Graph(directed=self.global_config.is_directed_graph)
        else:
            logger.info(
                f"Loaded graph from {self._graph_pickle_filename} with {preloaded_graph.vcount()} nodes, {preloaded_graph.ecount()} edges"
            )
            return preloaded_graph
    
    def save_igraph(self):
        """Save the graph to a pickle file."""
        logger.info(
            f"Writing graph with {len(self.graph.vs())} nodes, {len(self.graph.es())} edges"
        )
        self.graph.write_pickle(self._graph_pickle_filename)
        logger.info(f"Saving graph completed!")
    
    def get_graph_info(self) -> Dict:
        """
        Obtains detailed information about the graph such as the number of nodes,
        triples, and their classifications.

        This method calculates various statistics about the graph based on the
        stores and node-to-node relationships, including counts of phrase and
        passage nodes, total nodes, extracted triples, triples involving passage
        nodes, synonymy triples, and total triples.

        Returns:
            Dict: A dictionary containing graph statistics:
                - num_phrase_nodes: The number of unique phrase nodes.
                - num_passage_nodes: The number of unique passage nodes.
                - num_total_nodes: The total number of nodes (sum of phrase and passage nodes).
                - num_extracted_triples: The number of unique extracted triples.
                - num_triples_with_passage_node: The number of triples involving at least one
                  passage node.
                - num_synonymy_triples: The number of synonymy triples (distinct from extracted
                  triples and those with passage nodes).
                - num_total_triples: The total number of triples.
        """
        graph_info = {}

        # get # of phrase nodes
        phrase_nodes_keys = self.entity_embedding_store.get_all_ids()
        graph_info["num_phrase_nodes"] = len(set(phrase_nodes_keys))

        # get # of passage nodes
        passage_nodes_keys = self.chunk_embedding_store.get_all_ids()
        graph_info["num_passage_nodes"] = len(set(passage_nodes_keys))

        # get # of total nodes
        graph_info["num_total_nodes"] = graph_info["num_phrase_nodes"] + graph_info["num_passage_nodes"]

        # get # of extracted triples
        graph_info["num_extracted_triples"] = len(self.fact_embedding_store.get_all_ids())

        num_triples_with_passage_node = 0
        passage_nodes_set = set(passage_nodes_keys)
        num_triples_with_passage_node = sum(
            1 for node_pair in self.node_to_node_stats
            if node_pair[0] in passage_nodes_set or node_pair[1] in passage_nodes_set
        )
        graph_info['num_triples_with_passage_node'] = num_triples_with_passage_node

        graph_info['num_synonymy_triples'] = len(self.node_to_node_stats) - graph_info[
            "num_extracted_triples"] - num_triples_with_passage_node

        # get # of total triples
        graph_info["num_total_triples"] = len(self.node_to_node_stats)

        return graph_info
    
    def augment_graph(self, graph_builder):
        """
        Provides utility functions to augment a graph by adding new nodes and edges.
        It ensures that the graph structure is extended to include additional components,
        and logs the completion status along with printing the updated graph information.
        
        Args:
            graph_builder: GraphBuilder instance to use for adding nodes and edges
        """
        graph_builder.add_new_nodes()
        graph_builder.add_new_edges()

        logger.info(f"Graph construction completed!")
        print(self.get_graph_info())


def create_graph_manager(global_config: BaseConfig,
                        working_dir: str,
                        graph: ig.Graph,
                        entity_embedding_store: EmbeddingStore,
                        chunk_embedding_store: EmbeddingStore,
                        fact_embedding_store: EmbeddingStore,
                        node_to_node_stats: Dict) -> GraphManager:
    """
    Factory function to create appropriate graph manager based on config.
    
    Parameters:
        global_config: BaseConfig instance
        working_dir: Working directory path
        graph: The igraph graph object
        entity_embedding_store: Entity embedding store
        chunk_embedding_store: Chunk embedding store
        fact_embedding_store: Fact embedding store
        node_to_node_stats: Dictionary mapping node pairs to statistics
    
    Returns:
        GraphManager or NebulaGraphManager instance
    """
    if global_config.use_nebula_graph:
        from .graph_manager_nebula import NebulaGraphManager
        return NebulaGraphManager(
            global_config=global_config,
            working_dir=working_dir,
            graph=graph,
            entity_embedding_store=entity_embedding_store,
            chunk_embedding_store=chunk_embedding_store,
            fact_embedding_store=fact_embedding_store,
            node_to_node_stats=node_to_node_stats
        )
    else:
        return GraphManager(
            global_config=global_config,
            working_dir=working_dir,
            graph=graph,
            entity_embedding_store=entity_embedding_store,
            chunk_embedding_store=chunk_embedding_store,
            fact_embedding_store=fact_embedding_store,
            node_to_node_stats=node_to_node_stats
        )

