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
        description="Qdrant Cluster Manager - Manage shards, snapshots, and cluster operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # === SHARD OPERATIONS ===
  # List all local shards from each peer
  qdrant-shard -ls

  # Move all shards from peer 1 to peer 2
  qdrant-shard -mv --from-peer 1 --to-peer 2

  # Replicate all shards from peer 1 to peer 2
  qdrant-shard -rs --from-peer 1 --to-peer 2

  # Abort an ongoing transfer
  qdrant-shard -abort --shard-id 0 --from-peer 1 --to-peer 2

  # === SNAPSHOT OPERATIONS ===
  # List snapshots for a collection (using env vars QDRANT_URL, QDRANT_PORT)
  qdrant-shard --snap-list -c my_collection

  # List snapshots using a specific public host
  qdrant-shard --snap-list -c my_collection -ph qdrant.example.com:6333
  qdrant-shard --snap-list -c my_collection -ph qdrant.example.com:443:https

  # List full (cluster) snapshots
  qdrant-shard --snap-list --full -ph qdrant.example.com:6333

  # Create a collection snapshot
  qdrant-shard --snap-create -c my_collection -ph qdrant.example.com:6333

  # Create a full cluster snapshot
  qdrant-shard --snap-create --full

  # Delete a snapshot
  qdrant-shard --snap-delete -c my_collection --snapshot-name snapshot-123.snapshot

  # Recover a collection from snapshot URL
  qdrant-shard --snap-recover -c my_collection --location https://server:6333/collections/col/snapshots/snap.snapshot

  # Recover with public host and authentication
  qdrant-shard --snap-recover -c my_collection -ph target-server:6333 --location https://source-server:6333/... --location-api-key SOURCE_API_KEY

  # Recover with priority
  qdrant-shard --snap-recover -c my_collection --location https://... --priority snapshot

  # Download a snapshot to local file
  qdrant-shard --snap-download -c my_collection --snapshot-name snapshot-123.snapshot --output ./backup.snapshot -ph qdrant.example.com:6333

Available transfer methods:
  - stream_records (default, best for most cases)
  - snapshot
  - wal_delta
  - resharding_stream_records

Available recovery priorities:
  - snapshot (default): Restore from snapshot, other nodes sync from this
  - replica: Prefer existing healthy replicas over snapshot
        """
    )
    
    # Operation type
    operation_group = parser.add_mutually_exclusive_group(required=True)
    
    # Shard operations
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
    
    # Snapshot operations
    operation_group.add_argument(
        "--snap-list",
        action="store_true",
        help="List snapshots (use -c for collection, --full for cluster snapshots)"
    )
    operation_group.add_argument(
        "--snap-create",
        action="store_true",
        help="Create a snapshot (use -c for collection, --full for cluster snapshot)"
    )
    operation_group.add_argument(
        "--snap-delete",
        action="store_true",
        help="Delete a snapshot (requires -c and --snapshot-name, or --full and --snapshot-name)"
    )
    operation_group.add_argument(
        "--snap-recover",
        action="store_true",
        help="Recover a collection from snapshot (requires -c and --location)"
    )
    operation_group.add_argument(
        "--snap-download",
        action="store_true",
        help="Download a snapshot file (requires -c and --snapshot-name)"
    )
    
    # Parameters for move/abort operations
    parser.add_argument(
        "--shard-id",
        type=str,
        help="ID(s) of the shard(s) to operate on. For -mv and -rs: comma-separated list (e.g., '1,2,3'). For -abort: single shard ID."
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
    
    # Snapshot parameters
    parser.add_argument(
        "-ph", "--public-host",
        type=str,
        help="Public host URL for snapshot operations. Supports multiple formats: "
             "'https://host:port', 'http://host:port', 'host:port', or 'host:port:https'. "
             "Examples: 'https://qdrant.example.com:6333', 'qdrant.example.com:6333', 'qdrant.example.com:443:https'"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use full (cluster) snapshots instead of collection snapshots"
    )
    parser.add_argument(
        "--snapshot-name",
        type=str,
        help="Name of the snapshot (for --snap-delete and --snap-download)"
    )
    parser.add_argument(
        "--location",
        type=str,
        help="Snapshot location URL or path (for --snap-recover)"
    )
    parser.add_argument(
        "--location-api-key",
        type=str,
        help="API key for authenticated snapshot URL (for --snap-recover)"
    )
    parser.add_argument(
        "--priority",
        type=str,
        choices=["snapshot", "replica"],
        default="snapshot",
        help="Recovery priority: 'snapshot' (restore from file) or 'replica' (prefer existing replicas)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path (for --snap-download)"
    )
    parser.add_argument(
        "--wait/--no-wait",
        dest="wait",
        action="store_true",
        default=True,
        help="Wait for operation to complete (default: True)"
    )
    parser.add_argument(
        "--snap-api-key",
        type=str,
        help="API key for the snapshot server (overrides QDRANT_API_KEY env var)"
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
    
    # Validate snapshot operations
    if args.snap_delete:
        if not args.snapshot_name:
            parser.error("--snapshot-name is required for --snap-delete")
    
    if args.snap_recover:
        if not args.location:
            parser.error("--location is required for --snap-recover")
        if args.full:
            parser.error("--snap-recover with --full is not supported via API. Use server restart with --snapshot-path instead.")
    
    if args.snap_download:
        if not args.snapshot_name:
            parser.error("--snapshot-name is required for --snap-download")
        if args.full:
            parser.error("--snap-download with --full is not yet supported")

