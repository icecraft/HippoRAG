"""
Adapter for igraph library to implement GraphInterface.
"""
import logging
from typing import Dict, List, Tuple, Optional, Any, Iterator
import igraph as ig

from .graph_interface import GraphInterface

logger = logging.getLogger(__name__)


class IGraphAdapter(GraphInterface):
    """
    Adapter for igraph library.
    Wraps igraph.Graph to implement GraphInterface.
    """
    
    def __init__(self, graph: ig.Graph):
        """
        Initialize adapter with an igraph graph.
        
        Args:
            graph: igraph.Graph instance
        """
        self._graph = graph
    
    def vcount(self) -> int:
        """Return the number of vertices in the graph."""
        return self._graph.vcount()
    
    def ecount(self) -> int:
        """Return the number of edges in the graph."""
        return self._graph.ecount()
    
    def add_vertices(self, n: int, attributes: Optional[Dict[str, List]] = None):
        """Add vertices to the graph."""
        if attributes:
            self._graph.add_vertices(n=n, attributes=attributes)
        else:
            self._graph.add_vertices(n)
    
    def add_edges(self, edges: List[Tuple[str, str]], attributes: Optional[Dict[str, List]] = None):
        """
        Add edges to the graph.
        
        Note: igraph expects edge indices, but we work with node names.
        This method converts node names to indices before adding edges.
        """
        # Convert node names to vertex indices
        name_to_idx = {v["name"]: idx for idx, v in enumerate(self._graph.vs) if "name" in v.attributes()}
        
        edge_indices = []
        for source_name, target_name in edges:
            if source_name in name_to_idx and target_name in name_to_idx:
                edge_indices.append((name_to_idx[source_name], name_to_idx[target_name]))
            else:
                logger.warning(f"Edge {source_name} -> {target_name} skipped: node not found")
        
        if edge_indices:
            if attributes:
                self._graph.add_edges(edge_indices, attributes=attributes)
            else:
                self._graph.add_edges(edge_indices)
    
    def get_vertices(self) -> Iterator[Any]:
        """Get an iterator over all vertices."""
        return iter(self._graph.vs)
    
    def get_edges(self) -> Iterator[Any]:
        """Get an iterator over all edges."""
        return iter(self._graph.es)
    
    def get_vertex_by_name(self, name: str) -> Optional[Any]:
        """Get a vertex by its name attribute."""
        try:
            vertices = self._graph.vs.select(name=name)
            if len(vertices) > 0:
                return vertices[0]
        except (KeyError, AttributeError):
            pass
        return None
    
    def get_vertex_attributes(self, attribute_name: str) -> List[Any]:
        """Get all values of a vertex attribute."""
        try:
            return self._graph.vs[attribute_name]
        except (KeyError, AttributeError):
            return []
    
    def is_directed(self) -> bool:
        """Return True if the graph is directed, False otherwise."""
        return self._graph.is_directed()
    
    def save(self, filename: str):
        """Save the graph to a pickle file."""
        self._graph.write_pickle(filename)
    
    @classmethod
    def load(cls, filename: str, directed: bool = True) -> 'IGraphAdapter':
        """Load a graph from a pickle file."""
        graph = ig.Graph.Read_Pickle(filename)
        return cls(graph)
    
    @classmethod
    def create(cls, directed: bool = True) -> 'IGraphAdapter':
        """Create a new empty graph."""
        graph = ig.Graph(directed=directed)
        return cls(graph)
    
    @property
    def native_graph(self) -> ig.Graph:
        """Get the underlying igraph.Graph object for direct access if needed."""
        return self._graph

