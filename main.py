"""
Qdrant Sharding Operations CLI

This is the command-line interface for Qdrant distributed cluster management.
It provides a thin wrapper around the qdrant_distributed package.

Documentation: https://api.qdrant.tech/master/api-reference/distributed/update-collection-cluster
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


from qdrant_distributed.constant import SHARED_COLLECTION_NAME
from qdrant_distributed.client.qdrant_client import QdrantClientManager
# Import refactored modules
from qdrant_distributed import ShardOperations, ClusterOperations
from qdrant_distributed.models import ShardTransferMethod, PeerInfo
from qdrant_distributed.exceptions import QdrantShardingError, ValidationError
from qdrant_distributed.cli import ResultFormatter, create_argument_parser
from qdrant_distributed.cli.parser import validate_args
from qdrant_distributed.config import MySQLManager
from qdrant_distributed.services.mysql_service import MySQLService
# Note: MongoDB support is deprecated - using MySQL by default
from typing import Dict, List
from qdrant_distributed.models.shard import ShardInfo


def convert_peer_shards_to_peer_info(peer_shards: Dict[int, List[ShardInfo]], peers_dict: Dict[str, any]) -> List[PeerInfo]:
    """
    Convert peer_shards dictionary to list of PeerInfo objects.
    
    Args:
        peer_shards: Dictionary mapping peer_id to list of ShardInfo objects
        peers_dict: Dictionary containing peer information with URIs
    
    Returns:
        List of PeerInfo objects
    """
    peer_info_list = []
    for peer_id, shards in peer_shards.items():
        # Get URI from peers_dict
        peer_data = peers_dict.get(str(peer_id), {})
        uri = peer_data.get("uri", "")
        
        peer_info = PeerInfo(
            peer_id=peer_id,
            uri=uri,
            local_shards=shards
        )
        peer_info_list.append(peer_info)
    
    return peer_info_list


def main() -> int:
    """
    Main entry point for Qdrant sharding operations CLI.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse command-line arguments
    parser = create_argument_parser(default_collection=SHARED_COLLECTION_NAME)
    args = parser.parse_args()
    
    # Validate arguments
    try:
        validate_args(parser, args)
    except SystemExit:
        return 1
    
    # Display operation header
    formatter = ResultFormatter()
    formatter.print_header("Qdrant Sharding Operations")
    print(f"Collection: {args.collection}")
    
    if args.list_shards:
        print("Operation: List Shards")
    else:
        if args.move_shard or args.replicate_shard:
            print(f"From Peer: {args.from_peer}")
            print(f"To Peer: {args.to_peer}")
            if args.shard_id:
                print(f"Shard IDs: {args.shard_id}")
            if args.move_shard:
                if args.shard_id:
                    print(f"Operation: Move Specific Shards (method: {args.method})")
                else:
                    print(f"Operation: Move All Shards (method: {args.method})")
            else:
                if args.shard_id:
                    print(f"Operation: Replicate Specific Shards (method: {args.method})")
                else:
                    print(f"Operation: Replicate All Shards (method: {args.method})")
        else:
            print(f"Shard ID: {args.shard_id}")
            print(f"From Peer: {args.from_peer}")
            print(f"To Peer: {args.to_peer}")
            print(f"Operation: Abort Transfer")
    
    if args.timeout:
        print(f"Timeout: {args.timeout}s")
    print("=" * 80)
    print()
    
    try:
        # Initialize QdrantClientManager (from existing configuration)
        print("[*] Initializing Qdrant client...")
        QdrantClientManager.initialize()
        print("[+] Qdrant client initialized")
        print()
        
        # Initialize MySQL if needed (MySQL is now the default for --save, -ml, --latest)
        mysql_service = None
        if args.save or args.last_mongo or args.latest:
            print("[*] Initializing MySQL connection...")
            MySQLManager.initialize()
            mysql_service = MySQLService()
            print("[+] MySQL connection initialized")
            print()
        
        # Initialize operations
        shard_ops = ShardOperations()
        cluster_ops = ClusterOperations()
        
        # Parse shard IDs if provided (comma-separated for move/replicate, single int for abort)
        shard_ids = None
        if args.shard_id:
            if args.move_shard or args.replicate_shard:
                # Parse comma-separated shard IDs
                try:
                    shard_ids = [int(sid.strip()) for sid in args.shard_id.split(',')]
                except ValueError:
                    formatter.print_error(
                        "Invalid Shard ID Format",
                        f"Shard IDs must be comma-separated integers (e.g., '1,2,3'). Got: {args.shard_id}",
                        ["Use format: --shard-id 1,2,3,4,5"]
                    )
                    return 1
        
        # Execute operation
        if args.move_shard:
            if shard_ids:
                print(f"[>] Moving shards {shard_ids} from peer {args.from_peer} to peer {args.to_peer}")
            else:
                print(f"[>] Moving all shards from peer {args.from_peer} to peer {args.to_peer}")
            print(f"   Method: {args.method}")
            print()
            
            # Get all shards from both peers
            if args.latest:
                print(f"📋 Getting shard information from MySQL (latest)...")
                all_peer_shards = mysql_service.get_latest_peers_as_dict()
                print(f"✓ Retrieved peer information from MySQL")
            else:
                print(f"📋 Getting shard information from peers...")
                all_peer_shards = cluster_ops.list_all_shards(
                    collection_name=args.collection,
                    timeout=args.timeout
                )
            print()
            
            # Use move_all to handle the entire workflow
            shard_ops.move_all(
                collection_name=args.collection,
                all_shards=all_peer_shards,
                from_peer_id=args.from_peer,
                to_peer_id=args.to_peer,
                method=ShardTransferMethod(args.method),
                timeout=args.timeout,
                shard_ids=shard_ids
            )
        
        elif args.replicate_shard:
            if shard_ids:
                print(f"[>] Replicating shards {shard_ids} from peer {args.from_peer} to peer {args.to_peer}")
            else:
                print(f"[>] Replicating all shards from peer {args.from_peer} to peer {args.to_peer}")
            print(f"   Method: {args.method}")
            print()
            
            # Get all shards from both peers
            if args.latest:
                print(f"📋 Getting shard information from MySQL (latest)...")
                all_peer_shards = mysql_service.get_latest_peers_as_dict()
                print(f"✓ Retrieved peer information from MySQL")
            else:
                print(f"📋 Getting shard information from peers...")
                all_peer_shards = cluster_ops.list_all_shards(
                    collection_name=args.collection,
                    timeout=args.timeout
                )
            print()
            
            # Use replicate_all to handle the entire workflow
            shard_ops.replicate_all(
                collection_name=args.collection,
                all_shards=all_peer_shards,
                from_peer_id=args.from_peer,
                to_peer_id=args.to_peer,
                method=ShardTransferMethod(args.method),
                timeout=args.timeout,
                shard_ids=shard_ids
            )
        
        elif args.abort_transfer:
            # For abort, shard_id should be a single integer
            if not args.shard_id or ',' in args.shard_id:
                formatter.print_error(
                    "Invalid Shard ID",
                    "For -abort operation, --shard-id must be a single integer",
                    ["Use format: --shard-id 1"]
                )
                return 1
            try:
                shard_id = int(args.shard_id)
            except ValueError:
                formatter.print_error(
                    "Invalid Shard ID",
                    f"Shard ID must be an integer. Got: {args.shard_id}",
                    ["Use format: --shard-id 1"]
                )
                return 1
            
            print(f"[!] Aborting transfer for shard {shard_id} from peer {args.from_peer} to peer {args.to_peer}")
            print()
            
            result = shard_ops.abort_transfer(
                collection_name=args.collection,
                shard_id=shard_id,
                from_peer_id=args.from_peer,
                to_peer_id=args.to_peer,
                timeout=args.timeout
            )
            
            formatter.print_operation_result(result)
        
        elif args.list_shards:
            if args.last_mongo:
                print(f"[*] Retrieving peer information from MySQL (latest)")
                print()
                
                # Fetch once and reuse to avoid duplicate queries
                latest_doc = mysql_service.get_latest_peers()
                peer_shards = mysql_service.get_latest_peers_as_dict(latest_doc)
                peer_uris = mysql_service.get_latest_peer_uris(latest_doc)
                formatter.print_shard_list(peer_shards, peer_uris)
            else:
                print(f"[*] Listing all local shards from each peer in the cluster")
                print()
                
                peer_shards = cluster_ops.list_all_shards(
                    collection_name=args.collection,
                    timeout=args.timeout
                )
                
                # Get peer URIs for display (cache for later use if saving)
                from qdrant_distributed.client import ClusterClient
                cluster_client = ClusterClient()
                peers_dict, _ = cluster_client.get_peers(args.timeout)
                peer_uris = {int(pid): peer_data.get("uri", "") for pid, peer_data in peers_dict.items()}
                
                formatter.print_shard_list(peer_shards, peer_uris)
                
                # Save to MySQL if requested (reuse cached peers_dict)
                if args.save:
                    print(f"\n[*] Saving peer information to MySQL...")
                    peer_info_list = convert_peer_shards_to_peer_info(peer_shards, peers_dict)
                    mysql_service.save_peers(peer_info_list)
                    print(f"[+] Peer information saved to MySQL")
        
        print("\n" + "=" * 80)
        print("[+] Operation completed")
        print("=" * 80)
        
        return 0
        
    except ValidationError as e:
        formatter.print_error(
            "Validation Error",
            str(e),
            ["Please check your input parameters and try again."]
        )
        return 1
        
    except QdrantShardingError as e:
        formatter.print_error(
            "Operation Failed",
            str(e),
            [
                "Qdrant server is running and accessible",
                "Collection exists",
                "Peer IDs are valid",
                "Shard ID exists in the collection"
            ]
        )
        return 1
        
    except Exception as e:
        formatter.print_error(
            "Unexpected Error",
            f"{type(e).__name__}: {e}"
        )
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

