"""
Abstract interface for graph libraries to enable interchangeable graph backends.
"""
from abc import ABC, abstractmethod
try:
    from abc import abstractclassmethod
except ImportError:
    # Python < 3.3 doesn't have abstractclassmethod
    from abc import abstractmethod as abstractclassmethod
from typing import Dict, List, Tuple, Optional, Any, Iterator
import numpy as np


class GraphInterface(ABC):
    """
    Abstract interface for graph operations.
    This allows swapping between different graph libraries (igraph, dgraph, etc.)
    """
    
    @abstractmethod
    def vcount(self) -> int:
        """Return the number of vertices in the graph."""
        pass
    
    @abstractmethod
    def ecount(self) -> int:
        """Return the number of edges in the graph."""
        pass
    
    @abstractmethod
    def add_vertices(self, n: int, attributes: Optional[Dict[str, List]] = None):
        """
        Add vertices to the graph.
        
        Args:
            n: Number of vertices to add
            attributes: Dictionary mapping attribute names to lists of values
        """
        pass
    
    @abstractmethod
    def add_edges(self, edges: List[Tuple[str, str]], attributes: Optional[Dict[str, List]] = None):
        """
        Add edges to the graph.
        
        Args:
            edges: List of (source, target) tuples, where source and target are node names
            attributes: Dictionary mapping attribute names to lists of values
        """
        pass
    
    @abstractmethod
    def get_vertices(self) -> Iterator[Any]:
        """
        Get an iterator over all vertices.
        
        Returns:
            Iterator over vertex objects that support attribute access via [] or .get()
        """
        pass
    
    @abstractmethod
    def get_edges(self) -> Iterator[Any]:
        """
        Get an iterator over all edges.
        
        Returns:
            Iterator over edge objects that support:
            - edge.source (vertex index or name)
            - edge.target (vertex index or name)
            - edge["attribute_name"] or edge.get("attribute_name")
        """
        pass
    
    @abstractmethod
    def get_vertex_by_name(self, name: str) -> Optional[Any]:
        """
        Get a vertex by its name attribute.
        
        Args:
            name: The name of the vertex
            
        Returns:
            Vertex object or None if not found
        """
        pass
    
    @abstractmethod
    def get_vertex_attributes(self, attribute_name: str) -> List[Any]:
        """
        Get all values of a vertex attribute.
        
        Args:
            attribute_name: Name of the attribute
            
        Returns:
            List of attribute values for all vertices
        """
        pass
    
    @abstractmethod
    def is_directed(self) -> bool:
        """Return True if the graph is directed, False otherwise."""
        pass
    
    @abstractmethod
    def save(self, filename: str):
        """
        Save the graph to a file.
        
        Args:
            filename: Path to save the graph
        """
        pass
    
    @abstractclassmethod
    def load(cls, filename: str, directed: bool = True) -> 'GraphInterface':
        """
        Load a graph from a file.
        
        Args:
            filename: Path to load the graph from
            directed: Whether the graph should be directed
            
        Returns:
            GraphInterface instance
        """
        pass
    
    @abstractclassmethod
    def create(cls, directed: bool = True) -> 'GraphInterface':
        """
        Create a new empty graph.
        
        Args:
            directed: Whether the graph should be directed
            
        Returns:
            GraphInterface instance
        """
        pass

    def delete_vertices(self, node_names: List[str]):
        """
        Delete vertices by their name attribute.
        Override in adapters that support vertex deletion.
        """
        raise NotImplementedError("delete_vertices is not supported by this graph backend")

    @abstractmethod
    def personalized_pagerank(self,
                             reset_prob: np.ndarray,
                             damping: float = 0.5,
                             weights: Optional[str] = 'weight') -> np.ndarray:
        """
        Run Personalized PageRank.
        
        Args:
            reset_prob: Reset probability for each vertex (index-aligned with get_vertices order)
            damping: Damping factor (alpha in standard PPR)
            weights: Edge attribute name for weights, or None for unweighted
        
        Returns:
            1D array of PPR scores, index-aligned with vertices
        """
        pass

