"""
Command-line argument parser.
"""

import argparse
from qdrant_distributed.models import ShardTransferMethod


def create_argument_parser(default_collection: str = "shared_vectors_hybrid") -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for CLI.
    
    Args:
        default_collection: Default collection name
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Qdrant Sharding Operations - Manage shard transfers and cluster operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # List all local shards from each peer
  python qdrant_sharding.py -list

  # List shards for a specific collection
  python qdrant_sharding.py -list --collection my_collection

  # Move all shards from peer 1 to peer 2 (using best method)
  python qdrant_sharding.py -mv --from-peer 1 --to-peer 2

  # Move all shards with specific method
  python qdrant_sharding.py -mv --from-peer 1 --to-peer 2 --method snapshot

  # Replicate all shards from peer 1 to peer 2
  python qdrant_sharding.py -rs --from-peer 1 --to-peer 2

  # Abort an ongoing transfer for a specific shard
  python qdrant_sharding.py -abort --shard-id 0 --from-peer 1 --to-peer 2

  # With custom timeout
  python qdrant_sharding.py -mv --from-peer 1 --to-peer 2 --timeout 60

Available transfer methods:
  - stream_records (default, best for most cases)
  - snapshot
  - wal_delta
  - resharding_stream_records
        """
    )
    
    # Operation type
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        "-mv", "--move-shard",
        action="store_true",
        help="Move all shards from one peer to another (only shards not already in destination)"
    )
    operation_group.add_argument(
        "-rs", "--replicate-shard",
        action="store_true",
        help="Replicate all shards from one peer to another (only shards not already in destination)"
    )
    operation_group.add_argument(
        "-abort", "--abort-transfer",
        action="store_true",
        help="Abort an ongoing shard transfer"
    )
    operation_group.add_argument(
        "-ls", "--list-shards",
        action="store_true",
        help="List all local shards from each peer in the cluster"
    )
    
    # Parameters for move/abort operations
    parser.add_argument(
        "--shard-id",
        type=int,
        help="ID of the shard to abort transfer (only used for -abort operation)"
    )

    parser.add_argument(
        "-fp", "--from-peer",
        type=int,
        help="Source peer ID (required for -mv, -rs, and -abort)"
    )
    parser.add_argument(
        "-tp", "--to-peer",
        type=int,
        help="Destination peer ID (required for -mv, -rs, and -abort)"
    )
    
    # Optional parameters
    parser.add_argument(
        "-c", "--collection",
        type=str,
        default=default_collection,
        help=f"Collection name (default: {default_collection})"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=ShardTransferMethod.list_methods(),
        default="stream_records",
        help="Transfer method for move/replicate operation (default: stream_records)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Operation timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save peer information to MongoDB after operation"
    )
    parser.add_argument(
        "-ml", "--last-mongo",
        action="store_true",
        dest="last_mongo",
        help="Retrieve and display peer information from MongoDB (only for -list operation)"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest peer information from MongoDB instead of querying (only for -mv and -rs operations)"
    )

    
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """
    Validate parsed arguments.
    
    Args:
        parser: ArgumentParser instance for error reporting
        args: Parsed arguments namespace
    
    Raises:
        SystemExit: If validation fails
    """
    # Validate required parameters for move/replicate operations
    if args.move_shard or args.replicate_shard:
        if args.from_peer is None:
            parser.error("--from-peer is required for -mv and -rs operations")
        if args.to_peer is None:
            parser.error("--to-peer is required for -mv and -rs operations")
    
    # Validate required parameters for abort operation
    if args.abort_transfer:
        if args.shard_id is None:
            parser.error("--shard-id is required for -abort operation")
        if args.from_peer is None:
            parser.error("--from-peer is required for -abort operation")
        if args.to_peer is None:
            parser.error("--to-peer is required for -abort operation")
    
    # Validate MongoDB-related flags
    if args.last_mongo and not args.list_shards:
        parser.error("-ml/--last-mongo can only be used with -list operation")
    
    if args.latest and not (args.move_shard or args.replicate_shard):
        parser.error("--latest can only be used with -mv or -rs operations")

