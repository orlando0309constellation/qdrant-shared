"""
Application State Management - Centralized state for the application.
"""

from typing import Optional, Dict, List, Set
import tkinter as tk
from typing import Optional, Dict, List, Set
import tkinter as tk
from qdrant_distributed.models.shard import ShardInfo
from qdrant_distributed.services.config_service import ConfigService
from qdrant_distributed.constant import SHARED_COLLECTION_NAME


class AppState:
    """Manages application state and variables."""
    
    def __init__(self):
        # Initialize configuration
        ConfigService.initialize()
        
        # UI Variables
        self.operation_var = tk.StringVar(value="list")
        self.collection_var = tk.StringVar(value=SHARED_COLLECTION_NAME)
        self.from_peer_var = tk.StringVar()
        self.to_peer_var = tk.StringVar()
        self.shard_id_var = tk.StringVar()
        self.method_var = tk.StringVar(value="stream_records")
        self.timeout_var = tk.StringVar(value="120")
        self.save_var = tk.BooleanVar(value=False)
        self.latest_var = tk.BooleanVar(value=False)
        self.last_mongo_var = tk.BooleanVar(value=False)
        
        # Configuration
        self.replicate_factor = ConfigService.get_int("replicate_factor", default=2)
        
        # Data storage
        self.current_peer_shards: Optional[Dict[int, List[ShardInfo]]] = None
        self.current_peer_uris: Optional[Dict[int, str]] = None
        
        # UI state
        self.selection_before_click: Set[str] = set()
        self.sort_reverse: Dict[str, bool] = {}
    
    def update_replicate_factor(self, value: int):
        """Update replicate factor and persist to database."""
        self.replicate_factor = value
        ConfigService.set_int("replicate_factor", value)

