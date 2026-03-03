"""
Adapter for dgraph library to implement GraphInterface.
"""
import logging
import json
import pickle
import uuid
from typing import Dict, List, Tuple, Optional, Any, Iterator
import numpy as np

try:
    import pydgraph
    DGRAPH_AVAILABLE = True
except ImportError:
    DGRAPH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("pydgraph library not installed. Install pydgraph to use DGraphAdapter.")

from .graph_interface import GraphInterface

logger = logging.getLogger(__name__)


class DGraphVertex:
    """Wrapper for dgraph vertex to provide igraph-like interface."""
    
    def __init__(self, uid: str, data: Dict[str, Any]):
        self.uid = uid
        self._data = data
    
    def __getitem__(self, key: str) -> Any:
        """Access vertex attribute like vertex['name']."""
        return self._data.get(key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get vertex attribute with default value."""
        return self._data.get(key, default)
    
    def attributes(self) -> List[str]:
        """Get list of attribute names."""
        return list(self._data.keys())


class DGraphEdge:
    """Wrapper for dgraph edge to provide igraph-like interface."""
    
    def __init__(self, source_uid: str, target_uid: str, source_name: str, target_name: str, 
                 data: Dict[str, Any], source_idx: int, target_idx: int):
        self.source_uid = source_uid
        self.target_uid = target_uid
        self.source_name = source_name
        self.target_name = target_name
        self._data = data
        self._source_idx = source_idx
        self._target_idx = target_idx
    
    @property
    def source(self) -> int:
        """Return source vertex index."""
        return self._source_idx
    
    @property
    def target(self) -> int:
        """Return target vertex index."""
        return self._target_idx
    
    def __getitem__(self, key: str) -> Any:
        """Access edge attribute like edge['weight']."""
        return self._data.get(key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get edge attribute with default value."""
        return self._data.get(key, default)
    
    def attributes(self) -> List[str]:
        """Get list of attribute names."""
        return list(self._data.keys())


class DGraphAdapter(GraphInterface):
    """
    Adapter for dgraph library.
    Wraps dgraph client to implement GraphInterface.
    """
    
    def __init__(self, client: Any = None, connection_config: Optional[Dict] = None, 
                 directed: bool = True, schema_initialized: bool = False):
        """
        Initialize adapter with dgraph connection.
        
        Args:
            client: pydgraph.DgraphClient instance (if provided)
            connection_config: Dictionary with dgraph connection parameters
                (e.g., {'host': 'localhost', 'port': 9080} or {'grpc': 'localhost:9080'})
            directed: Whether the graph is directed
            schema_initialized: Whether schema has been initialized
        """
        if not DGRAPH_AVAILABLE:
            raise ImportError("pydgraph library is not installed. Please install it to use DGraphAdapter.")
        
        self._directed = directed
        
        # Initialize dgraph client
        if client is not None:
            self._client = client
        elif connection_config:
            # Support both connection formats
            if 'grpc' in connection_config:
                grpc_address = connection_config['grpc']
            elif 'host' in connection_config and 'port' in connection_config:
                grpc_address = f"{connection_config['host']}:{connection_config['port']}"
            else:
                # Try pydgraph.open format
                if 'url' in connection_config:
                    grpc_address = connection_config['url'].replace('dgraph://', '')
                else:
                    raise ValueError("connection_config must contain 'grpc', ('host' and 'port'), or 'url'")
            
            client_stub = pydgraph.DgraphClientStub(grpc_address)
            self._client = pydgraph.DgraphClient(client_stub)
        else:
            raise ValueError("Either client or connection_config must be provided")
        
        # Cache for vertices and edges
        self._vertex_cache: Dict[str, DGraphVertex] = {}
        self._edge_cache: List[DGraphEdge] = []
        self._name_to_uid: Dict[str, str] = {}
        self._uid_to_idx: Dict[str, int] = {}
        self._idx_to_uid: Dict[int, str] = {}
        
        # Initialize schema if needed
        if not schema_initialized:
            self._init_schema()
    
    def _init_schema(self):
        """Initialize dgraph schema for nodes and edges."""
        schema = """
        name: string @index(exact) .
        node_type: string @index(exact) .
        content: string .
        properties: string .
        weight: float .
        edge_type: string .
        
        type Node {
            name
            node_type
            content
            properties
        }
        """
        try:
            self._client.alter(pydgraph.Operation(schema=schema))
            logger.info("Dgraph schema initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize dgraph schema (may already exist): {e}")
    
    def vcount(self) -> int:
        """Return the number of vertices in the graph."""
        query = """
        {
            total(func: type(Node)) {
                count(uid)
            }
        }
        """
        try:
            txn = self._client.txn(read_only=True)
            try:
                res = txn.query(query)
                data = json.loads(res.json)
                if "total" in data and len(data["total"]) > 0:
                    return data["total"][0].get("count", 0)
                return 0
            finally:
                txn.discard()
        except Exception as e:
            logger.error(f"Error counting vertices: {e}")
            # Fallback to cache if available
            if self._vertex_cache:
                return len(self._vertex_cache)
            return 0
    
    def ecount(self) -> int:
        """Return the number of edges in the graph."""
        # Count edges by querying for nodes with outgoing edges
        query = """
        {
            nodes(func: type(Node)) {
                Relation {
                    count(uid)
                }
            }
        }
        """
        try:
            txn = self._client.txn(read_only=True)
            try:
                res = txn.query(query)
                data = json.loads(res.json)
                total_edges = 0
                if "nodes" in data:
                    for node in data["nodes"]:
                        if "Relation" in node:
                            total_edges += len(node["Relation"])
                return total_edges
            finally:
                txn.discard()
        except Exception as e:
            logger.error(f"Error counting edges: {e}")
            # Fallback to cache if available
            if self._edge_cache:
                return len(self._edge_cache)
            return 0
    
    def add_vertices(self, n: int, attributes: Optional[Dict[str, List]] = None):
        """Add vertices to the graph."""
        if attributes is None:
            attributes = {}
        
        if n == 0:
            return
        
        # Prepare nodes for batch insertion
        # Use a unique identifier for each blank node
        nodes = []
        for i in range(n):
            blank_id = f"node_{uuid.uuid4().hex[:8]}"
            node = {
                "uid": f"_:{blank_id}",
                "dgraph.type": "Node"
            }
            for attr_name, attr_values in attributes.items():
                if i < len(attr_values):
                    node[attr_name] = attr_values[i]
            nodes.append((blank_id, node))
        
        # Insert nodes in batch
        txn = self._client.txn()
        try:
            for blank_id, node in nodes:
                response = txn.mutate(set_obj=node)
                # Update cache with new UIDs
                if response.uids and blank_id in response.uids:
                    uid = response.uids[blank_id]
                    if "name" in node:
                        self._name_to_uid[node["name"]] = uid
            txn.commit()
        except Exception as e:
            logger.error(f"Error adding vertices: {e}")
            txn.discard()
            raise
        finally:
            txn.discard()
        
        # Clear cache to force refresh
        self._vertex_cache.clear()
        self._uid_to_idx.clear()
        self._idx_to_uid.clear()
    
    def add_edges(self, edges: List[Tuple[str, str]], attributes: Optional[Dict[str, List]] = None):
        """Add edges to the graph."""
        if attributes is None:
            attributes = {}
        
        if not edges:
            return
        
        # Refresh name-to-uid mapping first
        if not self._name_to_uid:
            self._refresh_vertex_cache()
        
        # Get UIDs for source and target nodes
        txn = self._client.txn()
        try:
            for i, (source_name, target_name) in enumerate(edges):
                # Get UIDs for source and target
                source_uid = self._get_uid_by_name(source_name, txn)
                target_uid = self._get_uid_by_name(target_name, txn)
                
                if source_uid is None or target_uid is None:
                    logger.warning(f"Edge {source_name} -> {target_name} skipped: node not found")
                    continue
                
                # Create edge mutation
                edge_obj = {
                    "uid": target_uid
                }
                
                # Add edge attributes
                if "weight" in attributes and i < len(attributes["weight"]):
                    edge_obj["weight"] = attributes["weight"][i]
                if "edge_type" in attributes and i < len(attributes["edge_type"]):
                    edge_obj["edge_type"] = attributes["edge_type"][i]
                
                edge_data = {
                    "uid": source_uid,
                    "Relation": [edge_obj]
                }
                
                txn.mutate(set_obj=edge_data)
            
            txn.commit()
        except Exception as e:
            logger.error(f"Error adding edges: {e}")
            txn.discard()
            raise
        finally:
            txn.discard()
        
        # Clear edge cache
        self._edge_cache.clear()
    
    def _get_uid_by_name(self, name: str, txn: Any = None) -> Optional[str]:
        """Get UID by node name."""
        if name in self._name_to_uid:
            return self._name_to_uid[name]
        
        # Query dgraph for node with this name
        query = """
        query get_node($name: string) {
            nodes(func: eq(name, $name)) {
                uid
            }
        }
        """
        variables = {"$name": name}
        
        use_external_txn = txn is not None
        if not use_external_txn:
            txn = self._client.txn(read_only=True)
        
        try:
            res = txn.query(query, variables=variables)
            data = json.loads(res.json)
            if "nodes" in data and len(data["nodes"]) > 0:
                uid = data["nodes"][0]["uid"]
                self._name_to_uid[name] = uid
                return uid
        except Exception as e:
            logger.error(f"Error getting UID for node {name}: {e}")
        finally:
            if not use_external_txn:
                txn.discard()
        
        return None
    
    def _refresh_vertex_cache(self):
        """Refresh vertex cache from dgraph."""
        query = """
        {
            nodes(func: type(Node)) {
                uid
                name
                node_type
                content
                properties
            }
        }
        """
        txn = self._client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            self._vertex_cache.clear()
            self._name_to_uid.clear()
            self._uid_to_idx.clear()
            self._idx_to_uid.clear()
            
            if "nodes" in data:
                for idx, node_data in enumerate(data["nodes"]):
                    uid = node_data["uid"]
                    vertex = DGraphVertex(uid, node_data)
                    self._vertex_cache[uid] = vertex
                    if "name" in node_data:
                        self._name_to_uid[node_data["name"]] = uid
                    self._uid_to_idx[uid] = idx
                    self._idx_to_uid[idx] = uid
        finally:
            txn.discard()
    
    def _refresh_edge_cache(self):
        """Refresh edge cache from dgraph."""
        if not self._vertex_cache:
            self._refresh_vertex_cache()
        
        query = """
        {
            nodes(func: type(Node)) {
                uid
                name
                Relation {
                    uid
                    name
                    weight
                    edge_type
                }
            }
        }
        """
        txn = self._client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            self._edge_cache.clear()
            
            if "nodes" in data:
                for source_node in data["nodes"]:
                    source_uid = source_node["uid"]
                    source_name = source_node.get("name", "")
                    source_idx = self._uid_to_idx.get(source_uid, -1)
                    
                    if "Relation" in source_node:
                        for target_data in source_node["Relation"]:
                            target_uid = target_data["uid"]
                            target_name = target_data.get("name", "")
                            target_idx = self._uid_to_idx.get(target_uid, -1)
                            
                            edge_data = {}
                            if "weight" in target_data:
                                edge_data["weight"] = target_data["weight"]
                            if "edge_type" in target_data:
                                edge_data["edge_type"] = target_data["edge_type"]
                            
                            edge = DGraphEdge(
                                source_uid, target_uid, source_name, target_name,
                                edge_data, source_idx, target_idx
                            )
                            self._edge_cache.append(edge)
        finally:
            txn.discard()
    
    def get_vertices(self) -> Iterator[Any]:
        """Get an iterator over all vertices."""
        if not self._vertex_cache:
            self._refresh_vertex_cache()
        return iter(self._vertex_cache.values())
    
    def get_edges(self) -> Iterator[Any]:
        """Get an iterator over all edges."""
        if not self._edge_cache:
            self._refresh_edge_cache()
        return iter(self._edge_cache)
    
    def get_vertex_by_name(self, name: str) -> Optional[Any]:
        """Get a vertex by its name attribute."""
        if not self._vertex_cache:
            self._refresh_vertex_cache()
        
        uid = self._name_to_uid.get(name)
        if uid:
            return self._vertex_cache.get(uid)
        return None
    
    def get_vertex_attributes(self, attribute_name: str) -> List[Any]:
        """Get all values of a vertex attribute."""
        if not self._vertex_cache:
            self._refresh_vertex_cache()
        
        result = []
        for vertex in self._vertex_cache.values():
            value = vertex.get(attribute_name)
            if value is not None:
                result.append(value)
        return result
    
    def is_directed(self) -> bool:
        """Return True if the graph is directed, False otherwise."""
        return self._directed
    
    def save(self, filename: str):
        """
        Save the graph to a file.
        
        Note: Dgraph is a database, so we save a snapshot of the graph data.
        """
        # Export all graph data
        query = """
        {
            nodes(func: type(Node)) {
                uid
                name
                node_type
                content
                properties
                Relation {
                    uid
                    name
                    weight
                    edge_type
                }
            }
        }
        """
        txn = self._client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            
            # Save to pickle file
            with open(filename, 'wb') as f:
                pickle.dump({
                    'data': data,
                    'directed': self._directed,
                    'connection_config': self._get_connection_config()
                }, f)
        finally:
            txn.discard()
    
    def _get_connection_config(self) -> Dict:
        """Get connection configuration (for save/load)."""
        # Extract connection info from client stub if possible
        # This is a simplified version - you may need to store config separately
        return {}
    
    @classmethod
    def load(cls, filename: str, directed: bool = True, connection_config: Optional[Dict] = None) -> 'GraphInterface':
        """
        Load a graph from a file.
        
        Note: This loads data into dgraph, so connection_config is required.
        """
        if connection_config is None:
            raise ValueError("connection_config is required to load graph into dgraph")
        
        # Create adapter
        adapter = cls(connection_config=connection_config, directed=directed, schema_initialized=True)
        
        # Load data from file
        with open(filename, 'rb') as f:
            saved_data = pickle.load(f)
        
        data = saved_data.get('data', {})
        if 'nodes' not in data:
            return adapter
        
        # Reconstruct graph in dgraph
        # First, create all nodes and map old UIDs to new UIDs
        uid_mapping: Dict[str, str] = {}  # old_uid -> new_uid
        
        txn = adapter._client.txn()
        try:
            # Create all nodes first
            for node_data in data['nodes']:
                old_uid = node_data.get('uid', '')
                # Create node with blank UID
                blank_id = f"node_{uuid.uuid4().hex[:8]}"
                node_obj = {
                    "uid": f"_:{blank_id}",
                    "dgraph.type": "Node",
                    "name": node_data.get("name", ""),
                }
                if "node_type" in node_data:
                    node_obj["node_type"] = node_data["node_type"]
                if "content" in node_data:
                    node_obj["content"] = node_data["content"]
                if "properties" in node_data:
                    node_obj["properties"] = node_data["properties"]
                
                response = txn.mutate(set_obj=node_obj)
                
                # Map old UID to new UID
                if response.uids and blank_id in response.uids:
                    new_uid = response.uids[blank_id]
                    uid_mapping[old_uid] = new_uid
                    if "name" in node_data:
                        adapter._name_to_uid[node_data["name"]] = new_uid
            
            # Now create all edges using the UID mapping
            for node_data in data['nodes']:
                old_source_uid = node_data.get('uid', '')
                new_source_uid = uid_mapping.get(old_source_uid)
                
                if new_source_uid and "Relation" in node_data:
                    for target_data in node_data["Relation"]:
                        old_target_uid = target_data.get('uid', '')
                        new_target_uid = uid_mapping.get(old_target_uid)
                        
                        if new_target_uid:
                            edge_obj = {
                                "uid": new_target_uid
                            }
                            if "weight" in target_data:
                                edge_obj["weight"] = target_data["weight"]
                            if "edge_type" in target_data:
                                edge_obj["edge_type"] = target_data["edge_type"]
                            
                            edge_data = {
                                "uid": new_source_uid,
                                "Relation": [edge_obj]
                            }
                            txn.mutate(set_obj=edge_data)
            
            txn.commit()
        except Exception as e:
            logger.error(f"Error loading graph: {e}")
            txn.discard()
            raise
        finally:
            txn.discard()
        
        return adapter
    
    @classmethod
    def create(cls, directed: bool = True, connection_config: Optional[Dict] = None) -> 'DGraphAdapter':
        """Create a new empty graph."""
        if connection_config is None:
            # Default to localhost
            connection_config = {"host": "localhost", "port": 9080}
        return cls(connection_config=connection_config, directed=directed, schema_initialized=False)
    
    def delete_vertices(self, node_names: List[str]):
        """Delete vertices by name. Not yet implemented for DGraph."""
        raise NotImplementedError("delete_vertices not yet implemented for DGraphAdapter")

    @property
    def native_client(self) -> Any:
        """Get the underlying pydgraph.DgraphClient object for direct access if needed."""
        return self._client

    def personalized_pagerank(self,
                             reset_prob: np.ndarray,
                             damping: float = 0.5,
                             weights: Optional[str] = 'weight') -> np.ndarray:
        """Run Personalized PageRank by exporting to networkx and computing PPR."""
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx is required for PPR with DGraphAdapter. Install with: pip install networkx")
        
        if not self._vertex_cache:
            self._refresh_vertex_cache()
        if not self._edge_cache:
            self._refresh_edge_cache()
        
        # Build ordered vertex list (by index)
        n = len(self._vertex_cache)
        idx_to_name = {}
        for uid, idx in self._uid_to_idx.items():
            idx_to_name[idx] = self._vertex_cache[uid].get("name")
        
        names_ordered = [idx_to_name.get(i) for i in range(n) if idx_to_name.get(i) is not None]
        
        G = nx.DiGraph() if self._directed else nx.Graph()
        for v in self._vertex_cache.values():
            name = v.get("name")
            if name:
                G.add_node(name)
        
        for edge in self._edge_cache:
            src = edge.target_name or idx_to_name.get(edge.target)
            tgt = edge.source_name or idx_to_name.get(edge.source)
            if src and tgt:
                w = edge.get(weights, 1.0) if weights else 1.0
                G.add_edge(edge.source_name if hasattr(edge, 'source_name') else src,
                          edge.target_name if hasattr(edge, 'target_name') else tgt, weight=w)
        
        for edge in self._edge_cache:
            src_name = None
            tgt_name = None
            for uid, v in self._vertex_cache.items():
                if self._uid_to_idx.get(uid) == edge.source:
                    src_name = v.get("name")
                if self._uid_to_idx.get(uid) == edge.target:
                    tgt_name = v.get("name")
            if src_name and tgt_name:
                w = edge.get(weights, 1.0) if weights else 1.0
                G.add_edge(src_name, tgt_name, weight=w)
        
        # Simpler: iterate edges and use source/target names from DGraphEdge
        G = nx.DiGraph() if self._directed else nx.Graph()
        for v in self._vertex_cache.values():
            name = v.get("name")
            if name:
                G.add_node(name)
        for edge in self._edge_cache:
            sn = edge.source_name
            tn = edge.target_name
            if sn and tn:
                w = edge.get(weights, 1.0) if weights else 1.0
                G.add_edge(sn, tn, weight=w)
        
        # Build personalization dict (index -> name, reset_prob index-aligned)
        personalization = {}
        for idx in range(min(len(reset_prob), n)):
            name = idx_to_name.get(idx)
            if name and reset_prob[idx] > 0:
                personalization[name] = float(reset_prob[idx])
        
        if not personalization:
            first_name = idx_to_name.get(0)
            personalization = {first_name: 1.0} if first_name else {}
        
        total = sum(personalization.values())
        if total > 0:
            personalization = {k: v / total for k, v in personalization.items()}
        
        scores_dict = nx.pagerank(G, alpha=damping, personalization=personalization, weight=weights or 'weight')
        
        result = np.zeros(n, dtype=np.float64)
        for idx in range(n):
            name = idx_to_name.get(idx)
            if name:
                result[idx] = scores_dict.get(name, 0.0)
        
        return result
