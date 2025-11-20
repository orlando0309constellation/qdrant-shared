"""
Peer-related data models.
"""

from dataclasses import dataclass
from typing import List

from qdrant_distributed.models.shard import ShardInfo


@dataclass
class PeerInfo:
    """Information about a peer in the cluster."""
    
    peer_id: int
    uri: str
    local_shards: List[ShardInfo]
    
    @classmethod
    def from_dict(cls, peer_id: int, data: dict) -> "PeerInfo":
        """Create PeerInfo from dictionary response."""
        return cls(
            peer_id=peer_id,
            uri=data.get("uri", ""),
            local_shards=[]  # Will be populated separately
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "peer_id": self.peer_id,
            "uri": self.uri,
            "local_shards": [shard.to_dict() for shard in self.local_shards]
        }
    
    def get_shard_count(self) -> int:
        """Get total number of local shards."""
        return len(self.local_shards)
    
    def get_total_points(self) -> int:
        """Get total number of points across all local shards."""
        return sum(shard.points_count for shard in self.local_shards)
    
    def has_shard(self, shard_id: int) -> bool:
        """Check if peer has a specific shard."""
        return any(shard.shard_id == shard_id for shard in self.local_shards)

