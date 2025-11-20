"""
High-level cluster operations facade.
"""

from typing import Dict, List, Optional

from qdrant_distributed.services import ClusterService
from qdrant_distributed.models import ClusterInfo, ShardInfo
from qdrant_distributed.client import ClusterClient


class ClusterOperations:
    """
    High-level facade for cluster operations.
    
    This class provides a simplified interface for cluster monitoring
    and management operations.
    """
    
    def __init__(self, cluster_client: Optional[ClusterClient] = None):
        """
        Initialize cluster operations.
        
        Args:
            cluster_client: Optional cluster client instance
        """
        self.cluster_service = ClusterService(cluster_client)
    
    def get_info(self, timeout: Optional[int] = None) -> ClusterInfo:
        """
        Get cluster information.
        
        Args:
            timeout: Optional timeout in seconds
        
        Returns:
            ClusterInfo object with peer and cluster details
        
        Example:
            >>> ops = ClusterOperations()
            >>> info = ops.get_info()
            >>> print(f"Cluster has {info.get_peer_count()} peers")
        """
        return self.cluster_service.get_cluster_info(timeout)
    
    def list_all_shards(
        self,
        collection_name: str,
        timeout: Optional[int] = None
    ) -> Dict[int, List[ShardInfo]]:
        """
        List all local shards from each peer in the cluster.
        
        Args:
            collection_name: Name of the collection
            timeout: Optional timeout in seconds
        
        Returns:
            Dictionary mapping peer_id to list of ShardInfo objects
        
        Example:
            >>> ops = ClusterOperations()
            >>> shards = ops.list_all_shards("my_collection")
            >>> for peer_id, shard_list in shards.items():
            ...     print(f"Peer {peer_id}: {len(shard_list)} shards")
        """
        return self.cluster_service.get_all_peer_shards(collection_name, timeout)
    
    def get_shard_distribution(
        self,
        collection_name: str,
        timeout: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Get shard distribution statistics across the cluster.
        
        Args:
            collection_name: Name of the collection
            timeout: Optional timeout in seconds
        
        Returns:
            Dictionary with distribution statistics
        """
        peer_shards = self.list_all_shards(collection_name, timeout)
        
        total_shards = sum(len(shards) for shards in peer_shards.values())
        total_points = sum(
            sum(shard.points_count for shard in shards)
            for shards in peer_shards.values()
        )
        
        peer_stats = {}
        for peer_id, shards in peer_shards.items():
            peer_stats[peer_id] = {
                "shard_count": len(shards),
                "total_points": sum(shard.points_count for shard in shards),
                "shards": [shard.to_dict() for shard in shards]
            }
        
        return {
            "total_peers": len(peer_shards),
            "total_shards": total_shards,
            "total_points": total_points,
            "peers": peer_stats
        }

