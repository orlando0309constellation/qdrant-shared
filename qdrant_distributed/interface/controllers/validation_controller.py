"""
Validation Controller - Handles input validation and business rule validation.
"""

from typing import Dict, List, Optional, Tuple
from qdrant_distributed.models.shard import ShardInfo
from qdrant_distributed.interface.services.app_state import AppState


class ValidationController:
    """Handles validation logic for operations and inputs."""
    
    def __init__(self, app_state: AppState):
        self.app_state = app_state
    
    def validate_inputs(self) -> Tuple[bool, Optional[str]]:
        """Validate user inputs for current operation."""
        operation = self.app_state.operation_var.get()
        
        if operation in ["move", "replicate"]:
            if not self.app_state.from_peer_var.get() or not self.app_state.to_peer_var.get():
                return False, "From Peer and To Peer are required for move/replicate operations"
            try:
                int(self.app_state.from_peer_var.get())
                int(self.app_state.to_peer_var.get())
            except ValueError:
                return False, "Peer IDs must be integers"
                
        elif operation == "abort":
            if not self.app_state.from_peer_var.get() or not self.app_state.to_peer_var.get() or not self.app_state.shard_id_var.get():
                return False, "From Peer, To Peer, and Shard ID are required for abort operation"
            try:
                int(self.app_state.from_peer_var.get())
                int(self.app_state.to_peer_var.get())
                int(self.app_state.shard_id_var.get())
            except ValueError:
                return False, "Peer IDs and Shard ID must be integers"
        
        if self.app_state.last_mongo_var.get() and operation != "list":
            return False, "-ml (Load from MySQL) can only be used with List operation"
        
        if self.app_state.latest_var.get() and operation not in ["move", "replicate"]:
            return False, "--latest can only be used with Move or Replicate operations"
        
        try:
            int(self.app_state.timeout_var.get())
        except ValueError:
            return False, "Timeout must be an integer"
        
        return True, None
    
    def count_shard_copies(self, all_shards: Dict[int, List[ShardInfo]], 
                          shard_id: int, exclude_peer_id: Optional[int] = None) -> int:
        """Count the number of copies of a shard across all peers."""
        count = 0
        for peer_id, shards in all_shards.items():
            if exclude_peer_id is not None and peer_id == exclude_peer_id:
                continue
            if any(shard.shard_id == shard_id for shard in shards):
                count += 1
        return count
    
    def validate_replicate_factor(self, all_shards: Dict[int, List[ShardInfo]], 
                                  shard_ids: List[int], from_peer_id: int, 
                                  to_peer_id: int, operation: str) -> Tuple[bool, Optional[str]]:
        """Validate that replicating/moving shards won't exceed the replicate factor."""
        to_peer_shards = all_shards.get(to_peer_id, [])
        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}
        
        for shard_id in shard_ids:
            if shard_id in to_peer_shard_ids:
                continue
            
            if operation == "move":
                current_copies = self.count_shard_copies(all_shards, shard_id, exclude_peer_id=from_peer_id)
                if current_copies + 1 > self.app_state.replicate_factor:
                    return False, f"Shard {shard_id} would have {current_copies + 1} copies after move, which exceeds the replicate factor ({self.app_state.replicate_factor}). Cannot move."
            else:  # replicate
                current_copies = self.count_shard_copies(all_shards, shard_id)
                if current_copies + 1 > self.app_state.replicate_factor:
                    return False, f"Shard {shard_id} would have {current_copies + 1} copies after replicate, which exceeds the replicate factor ({self.app_state.replicate_factor}). Cannot replicate."
        
        return True, None

