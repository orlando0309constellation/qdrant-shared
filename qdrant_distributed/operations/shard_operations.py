"""
High-level shard operations facade.
"""

from typing import Dict, Any, List, Optional

from qdrant_distributed.models.shard import ShardInfo
from qdrant_distributed.services import ShardService
from qdrant_distributed.models import ShardTransferMethod
from qdrant_distributed.client import ClusterClient


class ShardOperations:
    """
    High-level facade for shard operations.
    
    This class provides a simplified interface for common shard operations,
    abstracting away the underlying service layer complexity.
    """
    
    def __init__(self, cluster_client: Optional[ClusterClient] = None):
        """
        Initialize shard operations.
        
        Args:
            cluster_client: Optional cluster client instance
        """
        self.shard_service = ShardService(cluster_client)
    
    def move(
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
        
        This is a convenience wrapper around the shard service move operation.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard to move
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            method: Optional transfer method (defaults to stream_records)
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary with status, result, and timing
        
        Example:
            >>> ops = ShardOperations()
            >>> result = ops.move("my_collection", 0, 1, 2)
            >>> print(f"Success: {result['result']}")
        """
        if method is None:
            method = ShardTransferMethod.get_default()
        
        return self.shard_service.move_shard(
            collection_name=collection_name,
            shard_id=shard_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            method=method,
            timeout=timeout
        )
    def move_all(self,collection_name:str,
    all_shards:Dict[int,
    List[ShardInfo]],
    from_peer_id:int,
    to_peer_id:int,
    method: Optional[ShardTransferMethod] = None,
    timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        from_peer_shards = all_shards.get(from_peer_id, [])
        to_peer_shards = all_shards.get(to_peer_id, [])

        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}

        print(f"   Found {len(from_peer_shards)} shards in peer {from_peer_id}")
        print(f"   Found {len(to_peer_shards)} shards in peer {to_peer_id}")

        shards_to_move = [shard for shard in from_peer_shards if shard.shard_id not in to_peer_shard_ids]

        results = []
        if not shards_to_move:
                print("✅ All shards from source peer are already in destination peer. Nothing to move.")
        else:
            print(f"📦 Moving {len(shards_to_move)} shard(s) that are not in destination peer...")
            print()
                
            for shard in shards_to_move:
                print(f"   Moving shard {shard.shard_id}...")
                try:
                    result = self.move(
                        collection_name=collection_name,
                        shard_id=shard.shard_id,
                        from_peer_id=from_peer_id,
                        to_peer_id=to_peer_id,
                        method=ShardTransferMethod(method),
                        timeout=timeout
                    )
                    results.append((shard.shard_id, result, None))
                    print(f"   ✅ Shard {shard.shard_id} moved successfully")
                except Exception as e:
                    error_msg = str(e)
                    results.append((shard.shard_id, None, error_msg))
                    print(f"   ❌ Shard {shard.shard_id} failed: {error_msg}")
                    print()
            
            # Print summary after all shards are processed
            successful = sum(1 for _, r, e in results if e is None)
            failed = len(results) - successful
            print(f"📊 Summary: {successful} successful, {failed} failed out of {len(results)} shard(s)")
        return results


    def replicate_all(self,collection_name:str,
    all_shards:Dict[int,
    List[ShardInfo]],
    from_peer_id:int,
    to_peer_id:int,
    method: Optional[ShardTransferMethod] = None,
    timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        from_peer_shards = all_shards.get(from_peer_id, [])
        to_peer_shards = all_shards.get(to_peer_id, [])

        to_peer_shard_ids = {shard.shard_id for shard in to_peer_shards}

        print(f"   Found {len(from_peer_shards)} shards in peer {from_peer_id}")
        print(f"   Found {len(to_peer_shards)} shards in peer {to_peer_id}")

        shards_to_replicate = [shard for shard in from_peer_shards if shard.shard_id not in to_peer_shard_ids]

        results = []
        if not shards_to_replicate:
                print("✅ All shards from source peer are already in destination peer. Nothing to replicate.")
        else:
            print(f"📦 Replicating {len(shards_to_replicate)} shard(s) that are not in destination peer...")
            print()
                
            for shard in shards_to_replicate:
                print(f"   Replicating shard {shard.shard_id}...")
                try:
                    result = self.replicate(
                        collection_name=collection_name,
                        shard_id=shard.shard_id,
                        from_peer_id=from_peer_id,
                        to_peer_id=to_peer_id,
                        method=ShardTransferMethod(method),
                        timeout=timeout
                    )
                    results.append((shard.shard_id, result, None))
                    print(f"   ✅ Shard {shard.shard_id} replicated successfully")
                except Exception as e:
                        error_msg = str(e)
                        results.append((shard.shard_id, None, error_msg))
                        print(f"   ❌ Shard {shard.shard_id} failed: {error_msg}")
                print()
            
            # Print summary after all shards are processed
            successful = sum(1 for _, r, e in results if e is None)
            failed = len(results) - successful
            print(f"📊 Summary: {successful} successful, {failed} failed out of {len(results)} shard(s)")
        return results

    def replicate(
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
            method: Optional transfer method (defaults to stream_records)
            timeout: Optional timeout in seconds
        
        Returns:
            Operation result dictionary
        """
        if method is None:
            method = ShardTransferMethod.get_default()
        
        return self.shard_service.replicate_shard(
            collection_name=collection_name,
            shard_id=shard_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            method=method,
            timeout=timeout
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
        return self.shard_service.abort_transfer(
            collection_name=collection_name,
            shard_id=shard_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            timeout=timeout
        )

