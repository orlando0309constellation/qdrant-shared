"""
Service for shard-related operations.
"""

from typing import Dict, Any, Optional

from qdrant_distributed.client import ClusterClient
from qdrant_distributed.models import ShardTransferMethod
from qdrant_distributed.models.shard import ShardTransferRequest


class ShardService:
    """Service for managing shard operations."""
    
    def __init__(self, cluster_client: Optional[ClusterClient] = None):
        """
        Initialize shard service.
        
        Args:
            cluster_client: Cluster client instance
        """
        self.cluster_client = cluster_client or ClusterClient()
    
    def move_shard(
        self,
        collection_name: str,
        shard_id: int,
        from_peer_id: int,
        to_peer_id: int,
        method: Optional[ShardTransferMethod] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Move a shard from one peer to another.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard to move
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            method: Optional transfer method
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary
        """
        # Validate inputs
        self.cluster_client._validate_collection_name(collection_name)
        self.cluster_client._validate_shard_id(shard_id)
        self.cluster_client._validate_peer_ids(from_peer_id, to_peer_id)
        
        # Build request
        request = ShardTransferRequest(
            shard_id=shard_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            method=method.value if method else None
        )
        
        # Create payload
        payload = {"move_shard": request.to_dict()}
        
        # Execute operation
        return self.cluster_client.update_collection_cluster(
            collection_name,
            payload,
            timeout
        )
    
    def replicate_shard(
        self,
        collection_name: str,
        shard_id: int,
        from_peer_id: int,
        to_peer_id: int,
        method: Optional[ShardTransferMethod] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Replicate a shard to another peer.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard to replicate
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            method: Optional transfer method
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary
        """
        # Validate inputs
        self.cluster_client._validate_collection_name(collection_name)
        self.cluster_client._validate_shard_id(shard_id)
        self.cluster_client._validate_peer_ids(from_peer_id, to_peer_id)
        
        # Build request
        request = ShardTransferRequest(
            shard_id=shard_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            method=method.value if method else None
        )
        
        # Create payload
        payload = {"replicate_shard": request.to_dict()}
        
        # Execute operation
        return self.cluster_client.update_collection_cluster(
            collection_name,
            payload,
            timeout
        )
    
    def abort_transfer(
        self,
        collection_name: str,
        shard_id: int,
        from_peer_id: int,
        to_peer_id: int,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Abort an ongoing shard transfer.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary
        """
        # Validate inputs
        self.cluster_client._validate_collection_name(collection_name)
        self.cluster_client._validate_shard_id(shard_id)
        self.cluster_client._validate_peer_ids(from_peer_id, to_peer_id)
        
        # Create payload
        payload = {
            "abort_transfer": {
                "shard_id": shard_id,
                "from_peer_id": from_peer_id,
                "to_peer_id": to_peer_id,
            }
        }
        
        # Execute operation
        return self.cluster_client.update_collection_cluster(
            collection_name,
            payload,
            timeout
        )

