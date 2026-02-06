from .graph_manager import GraphManager, create_graph_manager
from .graph_builder import GraphBuilder
from .graph_interface import GraphInterface
from .graph_factory import create_graph, wrap_graph
from .graph_adapter_igraph import IGraphAdapter

# Conditionally export DGraphAdapter if available
try:
    from .graph_adapter_dgraph import DGraphAdapter
    __all__ = [
        'GraphManager', 
        'create_graph_manager', 
        'GraphBuilder',
        'GraphInterface',
        'create_graph',
        'wrap_graph',
        'IGraphAdapter',
        'DGraphAdapter'
    ]
except ImportError:
    __all__ = [
        'GraphManager', 
        'create_graph_manager', 
        'GraphBuilder',
        'GraphInterface',
        'create_graph',
        'wrap_graph',
        'IGraphAdapter'
    ]
