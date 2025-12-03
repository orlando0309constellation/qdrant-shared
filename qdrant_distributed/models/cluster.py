"""
Cluster-related data models.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from qdrant_distributed.models.peer import PeerInfo
from qdrant_distributed.models.shard import ShardInfo


@dataclass
class ClusterInfo:
    """Information about the Qdrant cluster."""
    
    current_peer_id: Optional[int]
    peers: Dict[int, PeerInfo]
    status: str = "unknown"
    message_send_failures: Dict[str, Dict[str, any]] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClusterInfo":
        """Create ClusterInfo from dictionary response."""
        result = data.get("result", {})
        peers_data = result.get("peers", {})
        
        peers = {}
        for peer_id_str, peer_data in peers_data.items():
            peer_id = int(peer_id_str)
            peers[peer_id] = PeerInfo.from_dict(peer_id, peer_data)
        
        current_peer_id = result.get("peer_id")
        if current_peer_id is not None:
            current_peer_id = int(current_peer_id)
        
        # Extract message_send_failures if present
        message_send_failures = result.get("message_send_failures", {})
        if not message_send_failures:
            message_send_failures = None
        
        return cls(
            current_peer_id=current_peer_id,
            peers=peers,
            status=result.get("status", "unknown"),
            message_send_failures=message_send_failures
        )
    
    def get_peer_count(self) -> int:
        """Get total number of peers in cluster."""
        return len(self.peers)
    
    def get_all_peer_ids(self) -> List[int]:
        """Get list of all peer IDs."""
        peer_ids = list(self.peers.keys())
        if self.current_peer_id is not None and self.current_peer_id not in peer_ids:
            peer_ids.append(self.current_peer_id)
        return sorted(peer_ids)
    
    def get_peer(self, peer_id: int) -> Optional[PeerInfo]:
        """Get peer by ID."""
        return self.peers.get(peer_id)
    
    def get_total_shards(self) -> int:
        """Get total number of shards across all peers."""
        return sum(peer.get_shard_count() for peer in self.peers.values())
    
    def get_total_points(self) -> int:
        """Get total number of points across all peers."""
        return sum(peer.get_total_points() for peer in self.peers.values())

