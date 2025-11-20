"""
Shard-related data models.
"""

from dataclasses import dataclass
from typing import Optional

from qdrant_distributed.models.enums import ShardState


@dataclass
class ShardInfo:
    """Information about a shard."""
    
    shard_id: int
    points_count: int
    state: ShardState
    
    @classmethod
    def from_dict(cls, data: dict) -> "ShardInfo":
        """Create ShardInfo from dictionary response."""
        return cls(
            shard_id=data.get("shard_id", 0),
            points_count=data.get("points_count", 0),
            state=ShardState(data.get("state", "Active"))
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "shard_id": self.shard_id,
            "points_count": self.points_count,
            "state": self.state.value
        }
    
    def is_active(self) -> bool:
        """Check if shard is in active state."""
        return self.state == ShardState.ACTIVE


@dataclass
class ShardTransferRequest:
    """Request parameters for shard transfer operations."""
    
    shard_id: int
    from_peer_id: int
    to_peer_id: int
    method: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API request."""
        data = {
            "shard_id": self.shard_id,
            "from_peer_id": self.from_peer_id,
            "to_peer_id": self.to_peer_id,
        }
        if self.method:
            data["method"] = self.method
        return data

