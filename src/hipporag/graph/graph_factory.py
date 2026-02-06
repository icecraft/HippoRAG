"""
Factory for creating graph adapters based on configuration.
"""
import logging
from typing import Optional

from ..utils.config_utils import BaseConfig
from .graph_interface import GraphInterface

logger = logging.getLogger(__name__)


def create_graph(global_config: BaseConfig, directed: bool = True) -> GraphInterface:
    """
    Create a graph instance based on configuration.
    
    Args:
        global_config: BaseConfig instance with graph_library setting
        directed: Whether the graph should be directed
        
    Returns:
        GraphInterface instance (IGraphAdapter or DGraphAdapter)
    """
    graph_library = getattr(global_config, 'graph_library', 'igraph').lower()
    
    if graph_library == 'igraph':
        from .graph_adapter_igraph import IGraphAdapter
        return IGraphAdapter.create(directed=directed)
    
    elif graph_library == 'dgraph':
        from .graph_adapter_dgraph import DGraphAdapter
        connection_config = getattr(global_config, 'dgraph_config', None)
        return DGraphAdapter.create(directed=directed, connection_config=connection_config)
    
    else:
        logger.warning(f"Unknown graph_library '{graph_library}', defaulting to igraph")
        from .graph_adapter_igraph import IGraphAdapter
        return IGraphAdapter.create(directed=directed)


def wrap_graph(graph: any, global_config: Optional[BaseConfig] = None) -> GraphInterface:
    """
    Wrap an existing graph object (e.g., igraph.Graph) into a GraphInterface adapter.
    
    Args:
        graph: Existing graph object (e.g., igraph.Graph)
        global_config: Optional BaseConfig to determine adapter type
        
    Returns:
        GraphInterface instance wrapping the graph
    """
    # Try to detect graph type
    import igraph as ig
    
    if isinstance(graph, ig.Graph):
        from .graph_adapter_igraph import IGraphAdapter
        return IGraphAdapter(graph)
    
    # If it's already a GraphInterface, return as-is
    if isinstance(graph, GraphInterface):
        return graph
    
    # Default: try to wrap as igraph
    try:
        from .graph_adapter_igraph import IGraphAdapter
        return IGraphAdapter(graph)
    except Exception as e:
        logger.error(f"Failed to wrap graph object: {e}")
        raise ValueError(f"Cannot wrap graph object of type {type(graph)}")

