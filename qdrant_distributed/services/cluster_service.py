"""
Service for cluster-related operations.
"""

import asyncio
from typing import Dict, List, Optional

from qdrant_distributed.client import ClusterClient
from qdrant_distributed.client.qdrant_client import QdrantClientManager
from qdrant_distributed.models import ClusterInfo, PeerInfo, ShardInfo
from qdrant_distributed.services.migration_service import ensure_collection_exists


class ClusterService:
    """Service for managing cluster operations."""
    
    def __init__(self, cluster_client: Optional[ClusterClient] = None):
        """
        Initialize cluster service.
        
        Args:
            cluster_client: Cluster client instance
        """
        self.cluster_client = cluster_client or ClusterClient()
    
    def get_cluster_info(self, timeout: Optional[int] = None) -> ClusterInfo:
        """
        Get cluster information as a structured object.
        
        Args:
            timeout: Optional timeout in seconds
        
        Returns:
            ClusterInfo object
        """
        raw_info = self.cluster_client.get_cluster_info(timeout)
        return ClusterInfo.from_dict(raw_info)
    
    def get_all_peer_shards(
        self,
        collection_name: str,
        timeout: Optional[int] = None
    ) -> Dict[int, List[ShardInfo]]:
        """
        Get all local shards from each peer in the cluster.
        
        This method queries the collection cluster endpoint multiple times
        to collect shard information from all peers.
        
        Args:
            collection_name: Name of the collection
            timeout: Optional timeout in seconds
        
        Returns:
            Dictionary mapping peer_id to list of ShardInfo objects
        """
        self.cluster_client._validate_collection_name(collection_name)
        
        # Ensure collection exists before querying cluster info
        try:
            async_client = QdrantClientManager.get_async_client()
            if async_client:
                # Run async function in sync context
                try:
                    # Try to get existing event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, we can't use run_until_complete
                        # Create collection in a new thread with new event loop
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                asyncio.run,
                                ensure_collection_exists(async_client, collection_name, source_client=None)
                            )
                            future.result(timeout=30)
                    else:
                        # Loop exists but not running, use it
                        loop.run_until_complete(
                            ensure_collection_exists(async_client, collection_name, source_client=None)
                        )
                except RuntimeError:
                    # No event loop, create one
                    asyncio.run(
                        ensure_collection_exists(async_client, collection_name, source_client=None)
                    )
        except Exception as e:
            # Log but don't fail - collection might already exist or creation might fail
            # The actual cluster query will show the real error if collection doesn't exist
            print(f"⚠️  Warning: Could not ensure collection exists: {e}")
        
        # Get all peers
        peers, current_peer_id = self.cluster_client.get_peers(timeout)
        expected_peer_count = len(peers)
        
        # Collect shard info from peers
        peer_shards: Dict[int, List[ShardInfo]] = {}
        queried_peers = set()
        max_attempts = expected_peer_count * 2
        
        for attempt in range(max_attempts):
            result = self.cluster_client.get_peer_shards(collection_name, timeout)
            
            if result is None:
                break
            
            peer_id, local_shards = result
            
            # Skip if we already have this peer's info
            if peer_id in queried_peers:
                if len(queried_peers) >= expected_peer_count:
                    break
                continue
            
            # Store the peer's shard info
            peer_shards[peer_id] = local_shards
            queried_peers.add(peer_id)
            print(f"[+] Retrieved shard info from peer {peer_id} ({len(local_shards)} local shards)")
            
            # Stop if we've collected all peers
            if len(queried_peers) >= expected_peer_count:
                break
        
        # Normalize: ensure all known peers are in the result
        return self._normalize_peer_shards(peers, current_peer_id, peer_shards)
    
    @staticmethod
    def _normalize_peer_shards(
        peers: Dict[str, any],
        current_peer_id: Optional[int],
        peer_shards: Dict[int, List[ShardInfo]]
    ) -> Dict[int, List[ShardInfo]]:
        """
        Ensure all known peers are in the result dictionary.
        
        Args:
            peers: Dictionary of peer information from cluster
            current_peer_id: Current peer ID if available
            peer_shards: Dictionary of collected peer shards
        
        Returns:
            Normalized dictionary with all peer IDs included
        """
        all_peer_ids = {int(pid) for pid in peers.keys()}
        
        if current_peer_id is not None:
            all_peer_ids.add(int(current_peer_id))
        
        # Ensure all peers are in the result
        normalized = peer_shards.copy()
        for peer_id in all_peer_ids:
            if peer_id not in normalized:
                normalized[peer_id] = []
        
        return normalized

