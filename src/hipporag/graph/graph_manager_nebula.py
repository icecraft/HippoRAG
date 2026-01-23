import os
import logging
from typing import Dict, Optional
import igraph as ig
import json

from ..utils.config_utils import BaseConfig
from ..embedding_store import EmbeddingStore

logger = logging.getLogger(__name__)

try:
    from nebula3.gclient.net import ConnectionPool
    from nebula3.Config import Config
    from nebula3.common import ttypes
    NEBULA_AVAILABLE = True
except ImportError:
    NEBULA_AVAILABLE = False
    logger.warning("nebula3-python not installed. Nebula Graph support will be unavailable.")


class NebulaGraphManager:
    """
    GraphManager implementation using Nebula Graph for persistent storage.
    Still maintains in-memory igraph for computation (e.g., PPR).
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
        Initialize NebulaGraphManager.
        
        Args:
            global_config: Global configuration
            working_dir: Working directory path
            graph: The igraph graph object (kept in memory for computation)
            entity_embedding_store: Entity embedding store
            chunk_embedding_store: Chunk embedding store
            fact_embedding_store: Fact embedding store
            node_to_node_stats: Dictionary mapping node pairs to statistics
        """
        if not NEBULA_AVAILABLE:
            raise ImportError("nebula3-python is required for Nebula Graph support. Install it with: pip install nebula3-python")
        
        self.global_config = global_config
        self.working_dir = working_dir
        self.graph = graph
        self.entity_embedding_store = entity_embedding_store
        self.chunk_embedding_store = chunk_embedding_store
        self.fact_embedding_store = fact_embedding_store
        self.node_to_node_stats = node_to_node_stats
        
        # Nebula Graph connection config
        self.space_name = global_config.nebula_space_name
        self.addresses = [(global_config.nebula_host, global_config.nebula_port)]
        self.user = global_config.nebula_user
        self.password = global_config.nebula_password
        
        # Initialize connection pool
        self.config = Config()
        self.config.max_connection_pool_size = 10
        self.connection_pool = ConnectionPool()
        
        # Try to initialize connection
        try:
            ok = self.connection_pool.init(self.addresses, self.config)
            if not ok:
                raise RuntimeError(f"Failed to initialize Nebula Graph connection pool to {self.addresses}")
            logger.info(f"Initialized Nebula Graph connection pool to {self.addresses}")
        except Exception as e:
            logger.error(f"Error initializing Nebula Graph connection: {e}")
            raise
        
        # Initialize schema
        self._init_schema()
    
    def _init_schema(self):
        """Initialize Nebula Graph schema (space, tags, edge types)."""
        try:
            with self.connection_pool.session_context(self.user, self.password) as session:
                # Create space if not exists
                create_space_query = f"""
                CREATE SPACE IF NOT EXISTS {self.space_name} (
                    partition_num = 10,
                    replica_factor = 1,
                    vid_type = FIXED_STRING(256)
                );
                """
                result = session.execute(create_space_query)
                if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                    if "existed" not in result.error_msg:
                        logger.warning(f"Space creation result: {result.error_msg}")
                
                # Use the space
                session.execute(f"USE {self.space_name};")
                
                # Create Tag for nodes (Entity/Passage)
                create_tag_query = """
                CREATE TAG IF NOT EXISTS Node(
                    node_type string,
                    content string,
                    properties string
                );
                """
                result = session.execute(create_tag_query)
                if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                    if "existed" not in result.error_msg:
                        logger.warning(f"Tag creation result: {result.error_msg}")
                
                # Create Edge Type for relations
                create_edge_query = """
                CREATE EDGE IF NOT EXISTS Relation(
                    weight double,
                    edge_type string
                );
                """
                result = session.execute(create_edge_query)
                if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                    if "existed" not in result.error_msg:
                        logger.warning(f"Edge creation result: {result.error_msg}")
                
                # Create indexes for better query performance
                try:
                    session.execute(f"CREATE TAG INDEX IF NOT EXISTS node_name_index ON Node();")
                except:
                    pass  # Index might already exist
                
                logger.info(f"Initialized Nebula Graph schema for space {self.space_name}")
        except Exception as e:
            logger.error(f"Error initializing Nebula Graph schema: {e}")
            raise
    
    def initialize_graph(self) -> ig.Graph:
        """
        Initializes a graph by loading from Nebula Graph or creating a new one.
        Always returns an igraph object for computation compatibility.
        
        Returns:
            ig.Graph: A graph object (loaded from Nebula or newly created)
        """
        if self.global_config.force_index_from_scratch:
            logger.info("force_index_from_scratch is True, creating new graph")
            return ig.Graph(directed=self.global_config.is_directed_graph)
        
        # Try to load from Nebula Graph
        try:
            loaded_graph = self._load_from_nebula()
            if loaded_graph is not None:
                logger.info(
                    f"Loaded graph from Nebula Graph with {loaded_graph.vcount()} nodes, {loaded_graph.ecount()} edges"
                )
                return loaded_graph
        except Exception as e:
            logger.warning(f"Failed to load graph from Nebula Graph: {e}, creating new graph")
        
        # Create new graph if loading failed
        return ig.Graph(directed=self.global_config.is_directed_graph)
    
    def _load_from_nebula(self) -> Optional[ig.Graph]:
        """Load graph from Nebula Graph and convert to igraph."""
        try:
            with self.connection_pool.session_context(self.user, self.password) as session:
                session.execute(f"USE {self.space_name};")
                
                # Fetch all nodes using MATCH query
                fetch_nodes_query = "MATCH (n:Node) RETURN id(n) as vid, n.node_type as node_type, n.content as content;"
                result = session.execute(fetch_nodes_query)
                
                if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                    logger.error(f"Error fetching nodes: {result.error_msg}")
                    return None
                
                # Create igraph
                graph = ig.Graph(directed=self.global_config.is_directed_graph)
                
                # Add nodes
                node_vid_to_idx = {}
                node_attributes = {"name": []}
                
                for row in result:
                    try:
                        vid = None
                        # Parse row - Nebula returns ResultSet with rows
                        if hasattr(row, 'values'):
                            for val in row.values:
                                if hasattr(val, 'get_sVal'):
                                    vid = val.get_sVal().decode('utf-8')
                                    break
                                elif isinstance(val, (str, bytes)):
                                    vid = val.decode('utf-8') if isinstance(val, bytes) else val
                                    break
                    except Exception as e:
                        logger.warning(f"Error parsing node row: {e}")
                        continue
                    
                    if vid:
                        node_attributes["name"].append(vid)
                        node_vid_to_idx[vid] = len(node_attributes["name"]) - 1
                
                if len(node_attributes["name"]) > 0:
                    graph.add_vertices(n=len(node_attributes["name"]), attributes=node_attributes)
                else:
                    logger.info("No nodes found in Nebula Graph")
                    return None
                
                # Fetch all edges using MATCH query
                fetch_edges_query = "MATCH (a:Node)-[r:Relation]->(b:Node) RETURN id(a) as src, id(b) as dst, r.weight as weight;"
                result = session.execute(fetch_edges_query)
                
                if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                    logger.warning(f"Error fetching edges: {result.error_msg}")
                    return graph
                
                # Add edges
                edges = []
                edge_weights = {"weight": []}
                
                for row in result:
                    try:
                        src_vid = None
                        dst_vid = None
                        weight = 1.0
                        
                        if hasattr(row, 'values'):
                            values = list(row.values)
                            if len(values) >= 2:
                                # Extract src
                                src_val = values[0]
                                if hasattr(src_val, 'get_sVal'):
                                    src_vid = src_val.get_sVal().decode('utf-8')
                                elif isinstance(src_val, (str, bytes)):
                                    src_vid = src_val.decode('utf-8') if isinstance(src_val, bytes) else src_val
                                
                                # Extract dst
                                dst_val = values[1]
                                if hasattr(dst_val, 'get_sVal'):
                                    dst_vid = dst_val.get_sVal().decode('utf-8')
                                elif isinstance(dst_val, (str, bytes)):
                                    dst_vid = dst_val.decode('utf-8') if isinstance(dst_val, bytes) else dst_val
                                
                                # Extract weight
                                if len(values) > 2:
                                    weight_val = values[2]
                                    if hasattr(weight_val, 'get_dVal'):
                                        weight = weight_val.get_dVal()
                                    elif isinstance(weight_val, (int, float)):
                                        weight = float(weight_val)
                    except Exception as e:
                        logger.warning(f"Error parsing edge row: {e}")
                        continue
                    
                    if src_vid and dst_vid and src_vid in node_vid_to_idx and dst_vid in node_vid_to_idx:
                        src_idx = node_vid_to_idx[src_vid]
                        dst_idx = node_vid_to_idx[dst_vid]
                        edges.append((src_idx, dst_idx))
                        edge_weights["weight"].append(weight)
                
                if len(edges) > 0:
                    graph.add_edges(edges, attributes=edge_weights)
                
                return graph
        except Exception as e:
            logger.error(f"Error loading from Nebula Graph: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def save_igraph(self):
        """Save the graph to Nebula Graph."""
        logger.info(
            f"Writing graph with {len(self.graph.vs())} nodes, {len(self.graph.es())} edges to Nebula Graph"
        )
        
        try:
            with self.connection_pool.session_context(self.user, self.password) as session:
                session.execute(f"USE {self.space_name};")
                
                # Clear existing data if force_index_from_scratch
                if self.global_config.force_index_from_scratch:
                    logger.info("Clearing existing data in Nebula Graph")
                    session.execute("DELETE VERTEX *;")
                
                # Insert nodes in batches
                batch_size = 100
                nodes = list(self.graph.vs)
                
                entity_nodes = set(self.entity_embedding_store.get_all_ids())
                passage_nodes = set(self.chunk_embedding_store.get_all_ids())
                
                for i in range(0, len(nodes), batch_size):
                    batch = nodes[i:i + batch_size]
                    
                    for node in batch:
                        try:
                            node_name = node["name"]
                            
                            # Determine node type and content
                            if node_name in entity_nodes:
                                node_type = "entity"
                                row = self.entity_embedding_store.get_row(node_name)
                                content = row.get("content", "") if row else ""
                            elif node_name in passage_nodes:
                                node_type = "passage"
                                row = self.chunk_embedding_store.get_row(node_name)
                                content = row.get("content", "") if row else ""
                            else:
                                node_type = "unknown"
                                content = ""
                            
                            # Truncate content if too long (Nebula has string length limits)
                            if len(content) > 10000:
                                content = content[:10000] + "..."
                            
                            # Create properties JSON
                            props = json.dumps({"name": node_name}, ensure_ascii=False)
                            
                            # Use parameterized query style - escape single quotes for Nebula
                            node_name_clean = node_name.replace("'", "\\'")
                            content_clean = content.replace("'", "\\'").replace('"', '\\"')
                            props_clean = props.replace("'", "\\'").replace('"', '\\"')
                            
                            query = f"INSERT VERTEX Node(node_type, content, properties) VALUES \"{node_name_clean}\":(\"{node_type}\", \"{content_clean}\", \"{props_clean}\");"
                            
                            result = session.execute(query)
                            if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                                logger.warning(f"Error inserting node {node_name}: {result.error_msg}")
                        except Exception as e:
                            logger.warning(f"Error processing node {node.get('name', 'unknown')}: {e}")
                            continue
                
                # Insert edges in batches
                edges = list(self.graph.es)
                edge_batch_size = 100
                
                for i in range(0, len(edges), edge_batch_size):
                    batch = edges[i:i + edge_batch_size]
                    
                    for edge in batch:
                        try:
                            src_name = self.graph.vs[edge.source]["name"]
                            dst_name = self.graph.vs[edge.target]["name"]
                            weight = edge["weight"] if "weight" in edge.attributes() else 1.0
                            edge_type = "relation"  # Default edge type
                            
                            # Escape names
                            src_name_clean = src_name.replace("'", "\\'")
                            dst_name_clean = dst_name.replace("'", "\\'")
                            
                            query = f"INSERT EDGE Relation(weight, edge_type) VALUES \"{src_name_clean}\" -> \"{dst_name_clean}\":({weight}, \"{edge_type}\");"
                            
                            result = session.execute(query)
                            if result.error_code != ttypes.ErrorCode.SUCCEEDED:
                                # Skip if edge already exists
                                if "existed" not in result.error_msg.lower():
                                    logger.warning(f"Error inserting edge {src_name} -> {dst_name}: {result.error_msg}")
                        except Exception as e:
                            logger.warning(f"Error processing edge: {e}")
                            continue
                
                logger.info(f"Saving graph to Nebula Graph completed!")
        except Exception as e:
            logger.error(f"Error saving to Nebula Graph: {e}")
            raise
    
    def get_graph_info(self) -> Dict:
        """
        Obtains detailed information about the graph.
        Same implementation as base GraphManager.
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
        Same implementation as base GraphManager.
        """
        graph_builder.add_new_nodes()
        graph_builder.add_new_edges()
        
        logger.info(f"Graph construction completed!")
        print(self.get_graph_info())
    
    def close(self):
        """Close Nebula Graph connection pool."""
        if hasattr(self, 'connection_pool') and self.connection_pool:
            self.connection_pool.close()
            logger.info("Closed Nebula Graph connection pool")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()

