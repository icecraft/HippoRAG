"""
Adapter for igraph library to implement GraphInterface.

Wraps python-igraph to provide high-performance in-memory graph operations,
including native C-based Personalized PageRank via PRPack.
"""
import logging
from typing import Dict, List, Tuple, Optional, Any, Iterator
import numpy as np

try:
    import igraph as ig
    IGRAPH_AVAILABLE = True
except ImportError:
    IGRAPH_AVAILABLE = False

from .graph_interface import GraphInterface

logger = logging.getLogger(__name__)


class IGraphAdapter(GraphInterface):
    """
    Adapter for igraph library.
    Wraps igraph.Graph to implement GraphInterface with native C-based PPR.
    """

    def __init__(self, graph: Any = None, directed: bool = True):
        """
        Initialize adapter with an igraph.Graph instance.

        Args:
            graph: igraph.Graph instance (if None, creates empty graph)
            directed: Whether the graph is directed
        """
        if not IGRAPH_AVAILABLE:
            raise ImportError("igraph library is not installed. Install with: pip install igraph")

        if graph is not None:
            self._graph = graph
        else:
            self._graph = ig.Graph(directed=directed)

    def vcount(self) -> int:
        """Return the number of vertices in the graph."""
        return self._graph.vcount()

    def ecount(self) -> int:
        """Return the number of edges in the graph."""
        return self._graph.ecount()

    def add_vertices(self, n: int, attributes: Optional[Dict[str, List]] = None, book_id: Optional[str] = None):
        """Add vertices to the graph.

        Args:
            n: Number of vertices to add
            attributes: Dict of attribute name to list of values
            book_id: Optional book identifier (stored as vertex attribute)
        """
        if n == 0:
            return

        attrs = attributes if attributes is not None else {}
        if book_id and "book_id" not in attrs:
            attrs["book_id"] = [book_id] * n

        self._graph.add_vertices(n, attributes=attrs)

    def add_edges(self, edges: List[Tuple[str, str]], attributes: Optional[Dict[str, List]] = None):
        """Add edges to the graph.

        Args:
            edges: List of (source_name, target_name) tuples
            attributes: Dict of attribute name to list of values
        """
        if not edges:
            return

        self._graph.add_edges(edges, attributes=attributes or {})

    def get_vertices(self) -> Iterator[Any]:
        """Get an iterator over all vertices."""
        return iter(self._graph.vs)

    def get_edges(self) -> Iterator[Any]:
        """Get an iterator over all edges."""
        return iter(self._graph.es)

    def get_vertex_by_name(self, name: str) -> Optional[Any]:
        """Get a vertex by its name attribute."""
        try:
            vs = self._graph.vs.find(name=name)
            return vs
        except ValueError:
            return None

    def get_vertex_attributes(self, attribute_name: str) -> List[Any]:
        """Get all values of a vertex attribute."""
        if self._graph.vcount() == 0:
            return []
        try:
            return self._graph.vs[attribute_name]
        except AttributeError:
            return []

    def is_directed(self) -> bool:
        """Return True if the graph is directed, False otherwise."""
        return self._graph.is_directed()

    def save(self, filename: str):
        """Save the graph to a pickle file."""
        logger.info(f"Writing graph with {self._graph.vcount()} nodes, {self._graph.ecount()} edges")
        self._graph.write_pickle(filename)
        logger.info(f"Saving graph to {filename} completed!")

    @classmethod
    def load(cls, filename: str, directed: bool = True, **kwargs) -> 'IGraphAdapter':
        """Load a graph from a pickle file.

        Args:
            filename: Path to the pickle file
            directed: Ignored (directed state is stored in pickle)

        Returns:
            IGraphAdapter instance
        """
        if not IGRAPH_AVAILABLE:
            raise ImportError("igraph library is not installed.")
        graph = ig.Graph.Read_Pickle(filename)
        return cls(graph=graph, directed=graph.is_directed())

    @classmethod
    def create(cls, directed: bool = True, **kwargs) -> 'IGraphAdapter':
        """Create a new empty graph."""
        if not IGRAPH_AVAILABLE:
            raise ImportError("igraph library is not installed.")
        return cls(directed=directed)

    def delete_vertices(self, node_names: List[str]):
        """Delete vertices by name."""
        indices_to_delete = []
        for name in node_names:
            try:
                v = self._graph.vs.find(name=name)
                indices_to_delete.append(v.index)
            except ValueError:
                logger.warning(f"Vertex {name} not found, skipping deletion")

        if indices_to_delete:
            self._graph.delete_vertices(indices_to_delete)

    @property
    def native_client(self) -> Any:
        """Get the underlying igraph.Graph object for direct access if needed."""
        return self._graph

    def personalized_pagerank(self,
                              reset_prob: np.ndarray,
                              damping: float = 0.5,
                              weights: Optional[str] = 'weight') -> np.ndarray:
        """Run Personalized PageRank using igraph's native C implementation (PRPack).

        This is significantly faster than networkx-based PPR (~250x on large graphs).

        Args:
            reset_prob: Reset probability for each vertex (index-aligned with vertices)
            damping: Damping factor (alpha in standard PPR)
            weights: Edge attribute name for weights, or None for unweighted

        Returns:
            1D array of PPR scores, index-aligned with vertices
        """
        n = self._graph.vcount()

        if n == 0:
            return np.array([], dtype=np.float64)

        reset_prob = np.where(np.isnan(reset_prob) | (reset_prob < 0), 0, reset_prob)

        pagerank_scores = self._graph.personalized_pagerank(
            vertices=range(n),
            damping=damping,
            directed=False,
            weights=weights,
            reset=reset_prob,
            implementation='prpack'
        )

        return np.array(pagerank_scores, dtype=np.float64)
