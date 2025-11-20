"""
Client for cluster-specific API operations.
"""

from typing import Dict, Any, Optional, Tuple, List

from qdrant_distributed.client.http_client import QdrantHttpClient
from qdrant_distributed.models import ShardInfo
from qdrant_distributed.exceptions import QdrantShardingError, ValidationError


class ClusterClient:
    """Client for Qdrant cluster operations."""
    
    def __init__(self, http_client: Optional[QdrantHttpClient] = None):
        """
        Initialize cluster client.
        
        Args:
            http_client: HTTP client instance (creates new if not provided)
        """
        self.http_client = http_client or QdrantHttpClient()
    
    def get_cluster_info(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Get cluster information.
        
        Args:
            timeout: Optional timeout in seconds
        
        Returns:
            Cluster information dictionary
        """
        return self.http_client.get("/cluster", timeout=timeout)
    
    def get_collection_cluster_info(
        self,
        collection_name: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get collection cluster information.
        
        Args:
            collection_name: Name of the collection
            timeout: Optional timeout in seconds
        
        Returns:
            Collection cluster information dictionary
        """
        self._validate_collection_name(collection_name)
        return self.http_client.get(
            f"/collections/{collection_name}/cluster",
            timeout=timeout
        )
    
    def update_collection_cluster(
        self,
        collection_name: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update collection cluster configuration.
        
        Args:
            collection_name: Name of the collection
            payload: Operation payload
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary
        """
        self._validate_collection_name(collection_name)
        return self.http_client.post(
            f"/collections/{collection_name}/cluster",
            payload=payload,
            timeout=timeout
        )
    
    def get_peers(self, timeout: Optional[int] = None) -> Tuple[Dict[str, Any], Optional[int]]:
        """
        Get cluster peers information.
        
        Args:
            timeout: Optional timeout in seconds
        
        Returns:
            Tuple of (peers_dict, current_peer_id)
        
        Raises:
            QdrantShardingError: If unable to get peer information
        """
        cluster_info = self.get_cluster_info(timeout)
        
        if "result" not in cluster_info:
            raise QdrantShardingError(
                f"Invalid cluster response: missing 'result' field. Response: {cluster_info}"
            )
        
        result = cluster_info["result"]
        peers = result.get("peers", {})
        
        if not peers:
            raise QdrantShardingError("No peers found in cluster")
        
        current_peer_id = result.get("peer_id")
        return peers, current_peer_id
    
    def get_peer_shards(
        self,
        collection_name: str,
        timeout: Optional[int] = None
    ) -> Optional[Tuple[int, List[ShardInfo]]]:
        """
        Get shard information from a responding peer.
        
        Args:
            collection_name: Name of the collection
            timeout: Optional timeout in seconds
        
        Returns:
            Tuple of (peer_id, list of ShardInfo) or None if failed
        """
        try:
            response = self.get_collection_cluster_info(collection_name, timeout)
            
            if "result" not in response:
                return None
            
            result = response["result"]
            peer_id = result.get("peer_id")
            
            if peer_id is None:
                return None
            
            local_shards_data = result.get("local_shards", [])
            local_shards = [ShardInfo.from_dict(shard) for shard in local_shards_data]
            
            return int(peer_id), local_shards
        except Exception as e:
            print(f"⚠️  Warning: Failed to query shard info: {e}")
            return None
    
    @staticmethod
    def _validate_collection_name(collection_name: str) -> None:
        """Validate collection name."""
        if not collection_name or not collection_name.strip():
            raise ValidationError("collection_name cannot be empty")
    
    @staticmethod
    def _validate_shard_id(shard_id: int) -> None:
        """Validate shard ID."""
        if shard_id < 0:
            raise ValidationError(f"shard_id must be non-negative, got {shard_id}")
    
    @staticmethod
    def _validate_peer_ids(from_peer_id: int, to_peer_id: int) -> None:
        """Validate peer IDs."""
        if from_peer_id < 0:
            raise ValidationError(f"from_peer_id must be non-negative, got {from_peer_id}")
        if to_peer_id < 0:
            raise ValidationError(f"to_peer_id must be non-negative, got {to_peer_id}")
        if from_peer_id == to_peer_id:
            raise ValidationError(
                f"from_peer_id and to_peer_id cannot be the same: {from_peer_id}"
            )

