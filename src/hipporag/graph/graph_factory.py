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
        GraphInterface instance (DGraphAdapter)
    """
    graph_library = getattr(global_config, 'graph_library', 'dgraph').lower()

    if graph_library == 'dgraph':
        from .graph_adapter_dgraph import DGraphAdapter
        connection_config = getattr(global_config, 'dgraph_config', None)
        return DGraphAdapter.create(directed=directed, connection_config=connection_config)

    logger.warning(f"Unknown graph_library '{graph_library}', defaulting to dgraph")
    from .graph_adapter_dgraph import DGraphAdapter
    connection_config = getattr(global_config, 'dgraph_config', None)
    return DGraphAdapter.create(directed=directed, connection_config=connection_config)


def wrap_graph(graph, global_config: Optional[BaseConfig] = None) -> GraphInterface:
    """
    Wrap an existing graph object into a GraphInterface adapter.

    If the graph is already a GraphInterface, returns it as-is.
    Otherwise raises ValueError (only DGraph/GraphInterface is supported).
    """
    if isinstance(graph, GraphInterface):
        return graph
    raise ValueError(f"Cannot wrap graph object of type {type(graph)}. Only GraphInterface is supported.")
