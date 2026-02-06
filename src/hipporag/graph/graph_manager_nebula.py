import os
import logging
import traceback
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
        
        # Initialize debug mode (only when MODE=DEBUG environment variable is set)
        self.debug_mode = os.getenv('MODE', '').upper() == 'DEBUG'
        if self.debug_mode:
            self.failed_nodes = []
            self.failed_edges = []
            self.debug_output_dir = os.path.join(working_dir, "nebula_debug")
            os.makedirs(self.debug_output_dir, exist_ok=True)
            logger.info("Debug mode enabled: failed insertions will be saved to local files")
        else:
            self.failed_nodes = None
            self.failed_edges = None
            self.debug_output_dir = None
    
    def _extract_error_context_chars(self, error_bytes: bytes, error_position: int, context_size: int = 5) -> Optional[str]:
        """
        Extract printable characters around the error position for easier debugging.
        
        Args:
            error_bytes: The raw error bytes
            error_position: The position where the error occurred
            context_size: Number of characters to extract before and after (default: 5)
        
        Returns:
            A string with context characters, or None if extraction fails
        """
        if error_position is None or not isinstance(error_bytes, bytes):
            return None
        
        try:
            # Try to decode with errors='replace' to get printable characters
            decoded = error_bytes.decode('utf-8', errors='replace')
            
            # Extract context around error position
            start = max(0, error_position - context_size)
            end = min(len(decoded), error_position + context_size + 1)
            context = decoded[start:end]
            
            # Replace non-printable characters with their hex representation
            result = []
            for i, char in enumerate(context):
                if char.isprintable() or char in '\n\r\t':
                    result.append(char)
                else:
                    # Show hex for non-printable characters
                    byte_pos = start + i
                    if byte_pos < len(error_bytes):
                        result.append(f'\\x{error_bytes[byte_pos]:02x}')
            
            return ''.join(result)
        except Exception:
            # If decoding fails, try to extract raw bytes and show hex
            try:
                start = max(0, error_position - context_size)
                end = min(len(error_bytes), error_position + context_size + 1)
                context_bytes = error_bytes[start:end]
                # Use simple hex() for compatibility (Python 3.5+)
                hex_str = context_bytes.hex()
                # Add spaces every 2 characters for readability
                hex_with_spaces = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
                return hex_with_spaces
            except Exception:
                return None
    
    def _get_error_code(self, result):
        """Get error_code from result (error_code is always a method in Nebula SDK)."""
        try:
            return result.error_code()
        except Exception:
            return None
    
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
                space_created = False
                err_code = self._get_error_code(result)
                if err_code != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(result.error_msg):
                            error_msg = result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    if not error_msg:
                        err_code = self._get_error_code(result)
                        error_msg = f"Error code: {err_code}" if err_code is not None else "Error code: unknown"
                    if "existed" not in error_msg.lower():
                        logger.warning(f"Space creation result: {error_msg}")
                else:
                    space_created = True
                    logger.info(f"Space {self.space_name} creation command executed successfully")
                
                # If space was just created, wait for it to be ready with retry
                if space_created:
                    import time
                    logger.info(f"Space {self.space_name} was created, waiting for it to be ready...")
                    max_retries = 10
                    retry_delay = 1  # Start with 1 second
                    for retry in range(max_retries):
                        time.sleep(retry_delay)
                        use_result = session.execute(f"USE {self.space_name};")
                        err_code = self._get_error_code(use_result)
                        if err_code == ttypes.ErrorCode.SUCCEEDED:
                            logger.info(f"Space {self.space_name} is ready after {retry + 1} attempt(s)")
                            break
                        else:
                            if retry < max_retries - 1:
                                logger.debug(f"Space not ready yet, retrying... (attempt {retry + 1}/{max_retries})")
                            else:
                                # Last attempt failed
                                try:
                                    if callable(use_result.error_msg):
                                        error_msg = use_result.error_msg()
                                        if isinstance(error_msg, bytes):
                                            error_msg = error_msg.decode('utf-8', errors='replace')
                                        else:
                                            error_msg = str(error_msg)
                                    else:
                                        error_msg = str(use_result.error_msg)
                                except (UnicodeDecodeError, AttributeError) as decode_err:
                                    error_msg = f"Error message decode failed: {decode_err}"
                                if not error_msg:
                                    err_code = self._get_error_code(use_result)
                                    error_msg = f"Error code: {err_code}" if err_code is not None else "Error code: unknown"
                                
                                # Log full traceback including Nebula SDK call stack
                                logger.error(f"Failed to use space {self.space_name} after {max_retries} attempts: {error_msg}")
                                logger.error("Full traceback:\n%s", traceback.format_exc())
                                raise RuntimeError(f"Failed to use space {self.space_name} after {max_retries} attempts: {error_msg}")
                else:
                    # Space already existed, just try to use it
                    use_result = session.execute(f"USE {self.space_name};")
                    err_code = self._get_error_code(use_result)
                    if err_code != ttypes.ErrorCode.SUCCEEDED:
                        try:
                            if callable(use_result.error_msg):
                                error_msg = use_result.error_msg()
                                if isinstance(error_msg, bytes):
                                    error_msg = error_msg.decode('utf-8', errors='replace')
                                else:
                                    error_msg = str(error_msg)
                            else:
                                error_msg = str(use_result.error_msg)
                        except (UnicodeDecodeError, AttributeError) as decode_err:
                            error_msg = f"Error message decode failed: {decode_err}"
                        if not error_msg:
                            err_code = self._get_error_code(use_result)
                            error_msg = f"Error code: {err_code}" if err_code is not None else "Error code: unknown"
                        
                        # Log full traceback including Nebula SDK call stack
                        logger.error(f"Failed to use space {self.space_name}: {error_msg}")
                        logger.error("Full traceback:\n%s", traceback.format_exc())
                        raise RuntimeError(f"Failed to use space {self.space_name}: {error_msg}")
                
                # Create Tag for nodes (Entity/Passage)
                create_tag_query = """
                CREATE TAG IF NOT EXISTS Node(
                    node_type string,
                    content string,
                    properties string
                );
                """
                result = session.execute(create_tag_query)
                if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(result.error_msg):
                            error_msg = result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    if "existed" not in error_msg:
                        logger.warning(f"Tag creation result: {error_msg}")
                
                # Create Edge Type for relations
                create_edge_query = """
                CREATE EDGE IF NOT EXISTS Relation(
                    weight double,
                    edge_type string
                );
                """
                result = session.execute(create_edge_query)
                if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(result.error_msg):
                            error_msg = result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    if "existed" not in error_msg:
                        logger.warning(f"Edge creation result: {error_msg}")
                
                # Create indexes for better query performance
                try:
                    session.execute(f"CREATE TAG INDEX IF NOT EXISTS node_name_index ON Node();")
                except:
                    pass  # Index might already exist
                
                logger.info(f"Initialized Nebula Graph schema for space {self.space_name}")
        except Exception as e:
            logger.error(f"Error initializing Nebula Graph schema: {e}")
            raise
    
    def _init_schema_in_session(self, session):
        """Initialize schema within an existing session (helper method)."""
        # Create Tag for nodes (Entity/Passage)
        create_tag_query = """
        CREATE TAG IF NOT EXISTS Node(
            node_type string,
            content string,
            properties string
        );
        """
        result = session.execute(create_tag_query)
        if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
            try:
                if callable(result.error_msg):
                    error_msg = result.error_msg()
                    if isinstance(error_msg, bytes):
                        error_msg = error_msg.decode('utf-8', errors='replace')
                    else:
                        error_msg = str(error_msg)
                else:
                    error_msg = str(result.error_msg)
            except (UnicodeDecodeError, AttributeError) as decode_err:
                error_msg = f"Error message decode failed: {decode_err}"
            if "existed" not in error_msg:
                logger.warning(f"Tag creation result: {error_msg}")
        
        # Create Edge Type for relations
        create_edge_query = """
        CREATE EDGE IF NOT EXISTS Relation(
            weight double,
            edge_type string
        );
        """
        result = session.execute(create_edge_query)
        if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
            try:
                if callable(result.error_msg):
                    error_msg = result.error_msg()
                    if isinstance(error_msg, bytes):
                        error_msg = error_msg.decode('utf-8', errors='replace')
                    else:
                        error_msg = str(error_msg)
                else:
                    error_msg = str(result.error_msg)
            except (UnicodeDecodeError, AttributeError) as decode_err:
                error_msg = f"Error message decode failed: {decode_err}"
            if "existed" not in error_msg:
                logger.warning(f"Edge creation result: {error_msg}")
        
        # Create indexes for better query performance
        try:
            session.execute(f"CREATE TAG INDEX IF NOT EXISTS node_name_index ON Node();")
        except:
            pass  # Index might already exist
    
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
                
                if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(result.error_msg):
                            error_msg = result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    logger.error(f"Error fetching nodes: {error_msg}")
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
                            # row.values might be a method or attribute
                            row_values = row.values() if callable(row.values) else row.values
                            if not isinstance(row_values, (list, tuple)):
                                row_values = list(row_values)
                            for val in row_values:
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
                
                if result.error_code() != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(result.error_msg):
                            error_msg = result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    logger.warning(f"Error fetching edges: {error_msg}")
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
                            # row.values might be a method or attribute
                            row_values = row.values() if callable(row.values) else row.values
                            values = list(row_values) if not isinstance(row_values, (list, tuple)) else row_values
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
        
        # Reset failed data lists if in debug mode
        if self.debug_mode:
            self.failed_nodes = []
            self.failed_edges = []
        
        try:
            with self.connection_pool.session_context(self.user, self.password) as session:
                # Use the space and verify it works
                use_result = session.execute(f"USE {self.space_name};")
                err_code = self._get_error_code(use_result)
                if err_code != ttypes.ErrorCode.SUCCEEDED:
                    try:
                        if callable(use_result.error_msg):
                            error_msg = use_result.error_msg()
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            else:
                                error_msg = str(error_msg)
                        else:
                            error_msg = str(use_result.error_msg)
                    except (UnicodeDecodeError, AttributeError) as decode_err:
                        error_msg = f"Error message decode failed: {decode_err}"
                    if not error_msg:
                        err_code = self._get_error_code(use_result)
                        error_msg = f"Error code: {err_code}" if err_code is not None else "Error code: unknown"
                    
                    # Log full traceback including Nebula SDK call stack
                    logger.error(f"Failed to use space {self.space_name}: {error_msg}")
                    logger.error("Full traceback:\n%s", traceback.format_exc())
                    raise RuntimeError(f"Failed to use space {self.space_name}: {error_msg}")
                
                # Verify schema exists by checking if Node tag exists
                check_tag_result = session.execute("SHOW TAGS;")
                check_tag_err_code = self._get_error_code(check_tag_result)
                if check_tag_err_code == ttypes.ErrorCode.SUCCEEDED:
                    tags = []
                    # Use ResultSet.keys() to get column names, then iterate rows
                    try:
                        # Method 1: Use keys() and column_values() (recommended in examples)
                        if hasattr(check_tag_result, 'keys'):
                            col_names = check_tag_result.keys()
                            if col_names and len(col_names) > 0:
                                col_name = col_names[0]  # Usually first column is the tag name
                                col_values = check_tag_result.column_values(col_name)
                                for val_wrapper in col_values:
                                    try:
                                        # Use as_string() method to get string value
                                        if hasattr(val_wrapper, 'as_string'):
                                            tag_name = val_wrapper.as_string()
                                        elif hasattr(val_wrapper, 'cast'):
                                            tag_name = str(val_wrapper.cast())
                                        else:
                                            tag_name = str(val_wrapper)
                                        # Remove quotes if present
                                        tag_name = tag_name.strip('"\'')
                                        if tag_name:
                                            tags.append(tag_name)
                                    except Exception as e:
                                        logger.debug(f"Error parsing tag value: {e}")
                                        continue
                        else:
                            # Fallback: iterate rows directly
                            for row in check_tag_result:
                                try:
                                    # Iterate columns in the row
                                    for col in row:
                                        try:
                                            if hasattr(col, 'as_string'):
                                                tag_name = col.as_string()
                                            elif hasattr(col, 'cast'):
                                                tag_name = str(col.cast())
                                            else:
                                                tag_name = str(col)
                                            # Remove quotes if present
                                            tag_name = tag_name.strip('"\'')
                                            if tag_name:
                                                tags.append(tag_name)
                                                break  # Only take first column
                                        except Exception as e:
                                            logger.debug(f"Error parsing tag column: {e}")
                                            continue
                                except Exception as e:
                                    logger.debug(f"Error parsing tag row: {e}")
                                    continue
                    except Exception as e:
                        logger.warning(f"Error parsing SHOW TAGS result: {e}")
                    
                    # Clean and check tags
                    tags = [t.strip('"\'') for t in tags if t]
                    if 'Node' not in tags:
                        logger.warning(f"Node tag not found in space {self.space_name}. Available tags: {tags}. Re-initializing schema...")
                        # Re-initialize schema in this session
                        self._init_schema_in_session(session)
                else:
                    logger.warning(f"Could not check tags, re-initializing schema...")
                    self._init_schema_in_session(session)
                
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
                            err_code = self._get_error_code(result)
                            if err_code != ttypes.ErrorCode.SUCCEEDED:
                                # Get error message safely
                                error_msg = None
                                error_bytes_hex = None
                                error_position = None
                                error_context = None
                                error_context_chars = None
                                
                                try:
                                    if callable(result.error_msg):
                                        error_msg_raw = result.error_msg()
                                        # Handle potential UnicodeDecodeError
                                        if isinstance(error_msg_raw, bytes):
                                            # Save raw bytes as hex for debugging
                                            error_bytes_hex = error_msg_raw.hex()
                                            
                                            # Try multiple encodings
                                            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                                                try:
                                                    error_msg = error_msg_raw.decode(encoding, errors='replace')
                                                    break
                                                except (UnicodeDecodeError, LookupError) as decode_err:
                                                    # Capture position information if it's a UnicodeDecodeError
                                                    if isinstance(decode_err, UnicodeDecodeError):
                                                        error_position = decode_err.start
                                                        # Save context around the problematic byte
                                                        start = max(0, decode_err.start - 10)
                                                        end = min(len(error_msg_raw), decode_err.end + 10)
                                                        error_context = error_msg_raw[start:end].hex()
                                                        # Extract printable characters around error position
                                                        error_context_chars = self._extract_error_context_chars(
                                                            error_msg_raw, error_position, context_size=5
                                                        )
                                                    continue
                                            if error_msg is None:
                                                # Fallback: use replace mode
                                                error_msg = error_msg_raw.decode('utf-8', errors='replace')
                                        else:
                                            error_msg = str(error_msg_raw)
                                    else:
                                        error_msg = str(result.error_msg)
                                except (UnicodeDecodeError, AttributeError, TypeError) as decode_err:
                                    # Capture detailed information about the decode error
                                    if isinstance(decode_err, UnicodeDecodeError):
                                        error_position = decode_err.start
                                        error_msg_raw = decode_err.object
                                        if isinstance(error_msg_raw, bytes):
                                            error_bytes_hex = error_msg_raw.hex()
                                            # Save context around the problematic byte
                                            start = max(0, decode_err.start - 10)
                                            end = min(len(error_msg_raw), decode_err.end + 10)
                                            error_context = error_msg_raw[start:end].hex()
                                            # Extract printable characters around error position
                                            error_context_chars = self._extract_error_context_chars(
                                                error_msg_raw, error_position, context_size=5
                                            )
                                    error_msg = f"Error message decode failed: {type(decode_err).__name__}: {decode_err}"
                                
                                if not error_msg:
                                    error_msg = f"Error code: {err_code}" if err_code is not None else "Unknown error"
                                
                                # Save failed node data if in debug mode
                                if self.debug_mode:
                                    failed_node_data = {
                                        "node_name": node_name,
                                        "node_type": node_type,
                                        "content_preview": content[:500] if len(content) > 500 else content,
                                        "content_length": len(content),
                                        "properties": props,
                                        "error_code": str(err_code) if err_code is not None else "unknown",
                                        "error_msg": error_msg,
                                        "query": query
                                    }
                                    
                                    # Add raw bytes information if available
                                    if error_bytes_hex:
                                        failed_node_data["error_bytes_hex"] = error_bytes_hex
                                    if error_position is not None:
                                        failed_node_data["error_position"] = error_position
                                    if error_context:
                                        failed_node_data["error_context_hex"] = error_context
                                    if error_context_chars:
                                        failed_node_data["error_context_chars"] = error_context_chars
                                    
                                    self.failed_nodes.append(failed_node_data)
                                
                                logger.warning(f"Error inserting node {node_name}: {error_msg}")
                        except Exception as e:
                            try:
                                node_name_for_log = node["name"] if "name" in node.attributes() else "unknown"
                            except:
                                node_name_for_log = "unknown"
                            logger.warning(f"Error processing node {node_name_for_log}: {e}")
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
                            err_code = self._get_error_code(result)
                            if err_code != ttypes.ErrorCode.SUCCEEDED:
                                # Skip if edge already exists
                                # Get error message safely
                                error_msg = None
                                error_bytes_hex = None
                                error_position = None
                                error_context = None
                                error_context_chars = None
                                
                                try:
                                    if callable(result.error_msg):
                                        error_msg_raw = result.error_msg()
                                        # Handle potential UnicodeDecodeError
                                        if isinstance(error_msg_raw, bytes):
                                            # Save raw bytes as hex for debugging
                                            error_bytes_hex = error_msg_raw.hex()
                                            
                                            # Try multiple encodings
                                            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                                                try:
                                                    error_msg = error_msg_raw.decode(encoding, errors='replace')
                                                    break
                                                except (UnicodeDecodeError, LookupError) as decode_err:
                                                    # Capture position information if it's a UnicodeDecodeError
                                                    if isinstance(decode_err, UnicodeDecodeError):
                                                        error_position = decode_err.start
                                                        # Save context around the problematic byte
                                                        start = max(0, decode_err.start - 10)
                                                        end = min(len(error_msg_raw), decode_err.end + 10)
                                                        error_context = error_msg_raw[start:end].hex()
                                                        # Extract printable characters around error position
                                                        error_context_chars = self._extract_error_context_chars(
                                                            error_msg_raw, error_position, context_size=5
                                                        )
                                                    continue
                                            if error_msg is None:
                                                # Fallback: use replace mode
                                                error_msg = error_msg_raw.decode('utf-8', errors='replace')
                                        else:
                                            error_msg = str(error_msg_raw)
                                    else:
                                        error_msg = str(result.error_msg)
                                except (UnicodeDecodeError, AttributeError, TypeError) as decode_err:
                                    # Capture detailed information about the decode error
                                    if isinstance(decode_err, UnicodeDecodeError):
                                        error_position = decode_err.start
                                        error_msg_raw = decode_err.object
                                        if isinstance(error_msg_raw, bytes):
                                            error_bytes_hex = error_msg_raw.hex()
                                            # Save context around the problematic byte
                                            start = max(0, decode_err.start - 10)
                                            end = min(len(error_msg_raw), decode_err.end + 10)
                                            error_context = error_msg_raw[start:end].hex()
                                            # Extract printable characters around error position
                                            error_context_chars = self._extract_error_context_chars(
                                                error_msg_raw, error_position, context_size=5
                                            )
                                    error_msg = f"Error message decode failed: {type(decode_err).__name__}: {decode_err}"
                                
                                if not error_msg:
                                    error_msg = f"Error code: {err_code}" if err_code is not None else "Unknown error"
                                
                                if "existed" not in error_msg.lower():
                                    # Save failed edge data if in debug mode
                                    if self.debug_mode:
                                        failed_edge_data = {
                                            "src_name": src_name,
                                            "dst_name": dst_name,
                                            "weight": weight,
                                            "edge_type": edge_type,
                                            "error_code": str(err_code) if err_code is not None else "unknown",
                                            "error_msg": error_msg,
                                            "query": query
                                        }
                                        
                                        # Add raw bytes information if available
                                        if error_bytes_hex:
                                            failed_edge_data["error_bytes_hex"] = error_bytes_hex
                                        if error_position is not None:
                                            failed_edge_data["error_position"] = error_position
                                        if error_context:
                                            failed_edge_data["error_context_hex"] = error_context
                                        if error_context_chars:
                                            failed_edge_data["error_context_chars"] = error_context_chars
                                        
                                        self.failed_edges.append(failed_edge_data)
                                    
                                    logger.warning(f"Error inserting edge {src_name} -> {dst_name}: {error_msg}")
                        except Exception as e:
                            logger.warning(f"Error processing edge: {e}")
                            continue
                
                logger.info(f"Saving graph to Nebula Graph completed!")
                
                # Save failed data to files if in debug mode
                if self.debug_mode:
                    self._save_failed_data()
        except Exception as e:
            logger.error(f"Error saving to Nebula Graph: {e}")
            # Even if exception occurs, try to save failed data if in debug mode
            if self.debug_mode:
                self._save_failed_data()
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
    
    def _save_failed_data(self):
        """Save failed insertion data to local files for debugging (only in DEBUG mode)."""
        if not self.debug_mode:
            return
        
        if not (self.failed_nodes or self.failed_edges):
            return
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Collect all error bytes for separate file
        error_bytes_list = []
        error_bytes_index = []
        
        if self.failed_nodes:
            failed_nodes_file = os.path.join(self.debug_output_dir, f"failed_nodes_{timestamp}.json")
            try:
                with open(failed_nodes_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "total_failed": len(self.failed_nodes),
                        "space_name": self.space_name,
                        "timestamp": timestamp,
                        "failed_nodes": self.failed_nodes
                    }, f, ensure_ascii=False, indent=2)
                logger.warning(f"[DEBUG] Saved {len(self.failed_nodes)} failed nodes to: {failed_nodes_file}")
                
                # Collect error bytes from nodes
                for idx, node_data in enumerate(self.failed_nodes):
                    if "error_bytes_hex" in node_data:
                        try:
                            error_bytes = bytes.fromhex(node_data["error_bytes_hex"])
                            error_position = node_data.get("error_position")
                            
                            # Extract context bytes (5 bytes before and after error position)
                            context_bytes = None
                            if error_position is not None:
                                context_start = max(0, error_position - 5)
                                context_end = min(len(error_bytes), error_position + 6)  # +6 to include the error byte and 5 after
                                context_bytes = error_bytes[context_start:context_end]
                            
                            error_bytes_list.append(error_bytes)
                            entry = {
                                "type": "node",
                                "index": idx,
                                "node_name": node_data.get("node_name", "unknown"),
                                "error_position": error_position,
                                "error_context_hex": node_data.get("error_context_hex"),
                                "error_context_chars": node_data.get("error_context_chars"),
                                "context_bytes": context_bytes  # Will be used when writing to file
                            }
                            error_bytes_index.append(entry)
                        except (ValueError, KeyError) as e:
                            logger.debug(f"Failed to parse error_bytes_hex for node {idx}: {e}")
            except Exception as e:
                logger.error(f"Failed to save failed nodes to file: {e}")
        
        if self.failed_edges:
            failed_edges_file = os.path.join(self.debug_output_dir, f"failed_edges_{timestamp}.json")
            try:
                with open(failed_edges_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "total_failed": len(self.failed_edges),
                        "space_name": self.space_name,
                        "timestamp": timestamp,
                        "failed_edges": self.failed_edges
                    }, f, ensure_ascii=False, indent=2)
                logger.warning(f"[DEBUG] Saved {len(self.failed_edges)} failed edges to: {failed_edges_file}")
                
                # Collect error bytes from edges
                for idx, edge_data in enumerate(self.failed_edges):
                    if "error_bytes_hex" in edge_data:
                        try:
                            error_bytes = bytes.fromhex(edge_data["error_bytes_hex"])
                            error_position = edge_data.get("error_position")
                            
                            # Extract context bytes (5 bytes before and after error position)
                            context_bytes = None
                            if error_position is not None:
                                context_start = max(0, error_position - 5)
                                context_end = min(len(error_bytes), error_position + 6)  # +6 to include the error byte and 5 after
                                context_bytes = error_bytes[context_start:context_end]
                            
                            error_bytes_list.append(error_bytes)
                            entry = {
                                "type": "edge",
                                "index": idx,
                                "src_name": edge_data.get("src_name", "unknown"),
                                "dst_name": edge_data.get("dst_name", "unknown"),
                                "error_position": error_position,
                                "error_context_hex": edge_data.get("error_context_hex"),
                                "error_context_chars": edge_data.get("error_context_chars"),
                                "context_bytes": context_bytes  # Will be used when writing to file
                            }
                            error_bytes_index.append(entry)
                        except (ValueError, KeyError) as e:
                            logger.debug(f"Failed to parse error_bytes_hex for edge {idx}: {e}")
            except Exception as e:
                logger.error(f"Failed to save failed edges to file: {e}")
        
        # Save all error bytes to a separate binary file
        if error_bytes_list:
            try:
                error_bytes_file = os.path.join(self.debug_output_dir, f"failed_error_bytes_{timestamp}.bin")
                error_bytes_index_file = os.path.join(self.debug_output_dir, f"failed_error_bytes_{timestamp}.json")
                
                separator = b'\xFF\xFF\xFF\xFF'  # 4-byte separator
                
                # Write binary file
                # Format for each entry: [full_error_bytes][separator][context_bytes]
                index_for_json = []
                with open(error_bytes_file, 'wb') as f:
                    for i, (error_bytes, index_entry) in enumerate(zip(error_bytes_list, error_bytes_index)):
                        # Calculate positions
                        current_pos = f.tell()
                        
                        # Write full error bytes
                        f.write(error_bytes)
                        full_bytes_start = current_pos
                        full_bytes_length = len(error_bytes)
                        
                        # Write context bytes if available
                        context_bytes = index_entry.get("context_bytes")
                        context_bytes_start = None
                        context_bytes_length = 0
                        if context_bytes:
                            f.write(separator)
                            context_bytes_start = f.tell()
                            f.write(context_bytes)
                            context_bytes_length = len(context_bytes)
                        
                        # Create index entry with positions
                        entry_copy = index_entry.copy()
                        entry_copy["full_bytes_start"] = full_bytes_start
                        entry_copy["full_bytes_length"] = full_bytes_length
                        if context_bytes:
                            entry_copy["context_bytes_start"] = context_bytes_start
                            entry_copy["context_bytes_length"] = context_bytes_length
                        # Remove context_bytes from JSON (it's in binary file)
                        if "context_bytes" in entry_copy:
                            del entry_copy["context_bytes"]
                        index_for_json.append(entry_copy)
                
                # Write index file
                with open(error_bytes_index_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "total_errors": len(error_bytes_list),
                        "space_name": self.space_name,
                        "timestamp": timestamp,
                        "binary_file": os.path.basename(error_bytes_file),
                        "file_format": "Each entry: [full_error_bytes][0xFFFFFFFF separator][context_bytes (5 bytes before/after error position)]",
                        "error_bytes_index": index_for_json
                    }, f, ensure_ascii=False, indent=2)
                
                logger.warning(f"[DEBUG] Saved {len(error_bytes_list)} error bytes (with context) to: {error_bytes_file}")
                logger.warning(f"[DEBUG] Saved error bytes index to: {error_bytes_index_file}")
            except Exception as e:
                logger.error(f"Failed to save error bytes to file: {e}")
    
    def close(self):
        """Close Nebula Graph connection pool."""
        if hasattr(self, 'connection_pool') and self.connection_pool:
            self.connection_pool.close()
            logger.info("Closed Nebula Graph connection pool")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()

