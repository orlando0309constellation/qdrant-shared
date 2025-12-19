"""
Qdrant Sharding Operations CLI

This is the command-line interface for Qdrant distributed cluster management.
It provides a thin wrapper around the qdrant_distributed package.

Documentation: https://api.qdrant.tech/master/api-reference/distributed/update-collection-cluster
"""

import os
import sys
import asyncio
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
from qdrant_distributed.services.snapshot_service import SnapshotService
# Note: MongoDB support is deprecated - using MySQL by default
from typing import Dict, List, Optional
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


def _get_snapshot_connection(args) -> tuple:
    """
    Get snapshot connection parameters from --public-host or environment variables.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Tuple of (url, port, https, api_key)
        
    Supported --public-host formats:
        - https://host:port  (full URL with scheme)
        - http://host:port   (full URL with scheme)
        - host:port:https    (simple format with https flag)
        - host:port          (simple format, defaults to http)
        - host               (just host, uses default port)
    """
    # Default from environment
    url = os.getenv("QDRANT_URL", "localhost")
    port = os.getenv("QDRANT_PORT", "6333")
    https = os.getenv("QDRANT_HTTPS", "false").lower() == "true"
    api_key = os.getenv("QDRANT_API_KEY")
    
    # Override with --public-host if provided
    if args.public_host:
        host_str = args.public_host.strip()
        
        # Check if it's a full URL (starts with http:// or https://)
        if host_str.startswith("https://"):
            https = True
            # Remove scheme
            host_str = host_str[8:]  # Remove "https://"
            # Parse host:port
            if ":" in host_str:
                parts = host_str.split(":")
                url = parts[0]
                port = parts[1].split("/")[0]  # Remove any path
            else:
                url = host_str.split("/")[0]  # Remove any path
                port = "443"  # Default HTTPS port
                
        elif host_str.startswith("http://"):
            https = False
            # Remove scheme
            host_str = host_str[7:]  # Remove "http://"
            # Parse host:port
            if ":" in host_str:
                parts = host_str.split(":")
                url = parts[0]
                port = parts[1].split("/")[0]  # Remove any path
            else:
                url = host_str.split("/")[0]  # Remove any path
                port = "6333"  # Default Qdrant port
        else:
            # Simple format: host:port or host:port:https
            parts = host_str.split(":")
            if len(parts) >= 2:
                url = parts[0]
                port = parts[1]
                # Check for https flag (third part)
                if len(parts) >= 3 and parts[2].lower() == "https":
                    https = True
                else:
                    https = False
            elif len(parts) == 1:
                url = parts[0]
    
    # Override API key if --snap-api-key provided
    if hasattr(args, 'snap_api_key') and args.snap_api_key:
        api_key = args.snap_api_key
    
    return url, port, https, api_key


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
    formatter.print_header("🔧 Qdrant Cluster Manager")
    
    # Determine operation type
    is_snapshot_op = any([args.snap_list, args.snap_create, args.snap_delete, args.snap_recover, args.snap_download])
    is_migration_op = any([args.migrate, args.migrate_usc, args.migrate_check])
    
    # Check if Rich is available for colored output
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        rich_console = Console()
        use_rich_output = True
    except ImportError:
        rich_console = None
        use_rich_output = False
    
    if is_migration_op:
        # Show migration operation info
        source_url = os.getenv("QDRANT_URL", "localhost")
        source_port = os.getenv("QDRANT_PORT", "6333")
        target_url = os.getenv("QDRANT_URL_2", "localhost")
        target_port = os.getenv("QDRANT_PORT_2", "6333")
        
        if use_rich_output and rich_console:
            info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
            info_table.add_column("Setting", style="cyan")
            info_table.add_column("Value", style="white")
            info_table.add_row("Source", f"{source_url}:{source_port}")
            info_table.add_row("Target", f"{target_url}:{target_port}")
            
            if args.migrate:
                info_table.add_row("Operation", "[bold cyan]Migrate All Collections[/bold cyan]")
            elif args.migrate_usc:
                info_table.add_row("Operation", "[bold cyan]Migrate Missing Collections Only[/bold cyan]")
            elif args.migrate_check:
                info_table.add_row("Operation", "[bold cyan]Check Synchronization[/bold cyan]")
                if args.check_count:
                    info_table.add_row("Mode", "[yellow]Detailed count check[/yellow]")
            
            direction = "[yellow]Reverse (target → source)[/yellow]" if args.reverse else "[green]Normal (source → target)[/green]"
            info_table.add_row("Direction", direction)
            
            https = getattr(args, 'migrate_https', True)
            https_status = "[green]Enabled[/green]" if https else "[yellow]Disabled[/yellow]"
            info_table.add_row("HTTPS", https_status)
            
            rich_console.print(info_table)
        else:
            print(f"Source: {source_url}:{source_port}")
            print(f"Target: {target_url}:{target_port}")
            
            if args.migrate:
                print("Operation: Migrate All Collections")
            elif args.migrate_usc:
                print("Operation: Migrate Missing Collections Only")
            elif args.migrate_check:
                print("Operation: Check Synchronization")
                if args.check_count:
                    print("Mode: Detailed count check")
            
            if args.reverse:
                print("Direction: Reverse (target → source)")
            else:
                print("Direction: Normal (source → target)")
            
            https = getattr(args, 'migrate_https', True)
            print(f"HTTPS: {https}")
    
    elif is_snapshot_op:
        # Show connection info for snapshot operations
        if args.public_host:
            print(f"Host: {args.public_host}")
        else:
            env_url = os.getenv("QDRANT_URL", "localhost")
            env_port = os.getenv("QDRANT_PORT", "6333")
            print(f"Host: {env_url}:{env_port} (from env)")
        
        print(f"Collection: {args.collection if not args.full else '(full/cluster)'}")
        if args.snap_list:
            print(f"Operation: List {'Full' if args.full else 'Collection'} Snapshots")
        elif args.snap_create:
            print(f"Operation: Create {'Full' if args.full else 'Collection'} Snapshot")
        elif args.snap_delete:
            print(f"Operation: Delete {'Full' if args.full else 'Collection'} Snapshot")
            print(f"Snapshot: {args.snapshot_name}")
        elif args.snap_recover:
            print(f"Operation: Recover Collection from Snapshot")
            print(f"Location: {args.location}")
            print(f"Priority: {args.priority}")
        elif args.snap_download:
            print(f"Operation: Download Snapshot")
            print(f"Snapshot: {args.snapshot_name}")
            if args.output:
                print(f"Output: {args.output}")
    elif not is_migration_op:
        # Shard operations (not migration, not snapshot)
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
        # Check if this is a snapshot operation (uses different initialization)
        is_snapshot_op = any([args.snap_list, args.snap_create, args.snap_delete, args.snap_recover, args.snap_download])
        is_migration_op = any([args.migrate, args.migrate_usc, args.migrate_check])
        
        # Handle migration operations
        if is_migration_op:
            # Import migration operations
            from qdrant_distributed.operations.migration_operations import MigrationOperations
            
            # Get configuration from environment variables
            source_url = os.getenv("QDRANT_URL", "localhost")
            source_port = int(os.getenv("QDRANT_PORT", "6333"))
            source_api_key = os.getenv("QDRANT_API_KEY")
            target_url = os.getenv("QDRANT_URL_2", "localhost")
            target_port = int(os.getenv("QDRANT_PORT_2", "6333"))
            target_api_key = os.getenv("QDRANT_API_KEY_2", os.getenv("QDRANT_API_KEY"))
            https = getattr(args, 'migrate_https', True)
            reverse = getattr(args, 'reverse', False)
            
            # Build configs
            source_config = {
                'url': source_url,
                'port': source_port,
                'api_key': source_api_key if source_api_key else None,
                'https': https
            }
            
            target_config = {
                'url': target_url,
                'port': target_port,
                'api_key': target_api_key if target_api_key else None,
                'https': https
            }
            
            # MySQL config - use default (None means use default from ConfigService)
            mysql_config = None
            
            print()
            print("[*] Starting migration operation...")
            print()
            
            # Set event loop policy for Windows
            if os.name == 'nt':  # Windows
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Create migration operations instance
            migration_ops = MigrationOperations()
            
            # Use the console we already created
            console = rich_console if use_rich_output else None
            use_rich = use_rich_output
            
            # Progress callback for simple CLI
            def progress_callback(collection_id: str, current: int, total: Optional[int]):
                if use_rich and console:
                    if total:
                        percentage = int((current / total) * 100)
                        console.print(f"  [cyan]Collection {collection_id}:[/cyan] [yellow]{current}/{total}[/yellow] [green]({percentage}%)[/green]")
                    else:
                        console.print(f"  [cyan]Collection {collection_id}:[/cyan] [yellow]{current}[/yellow] documents processed")
                else:
                    if total:
                        percentage = int((current / total) * 100)
                        print(f"  Collection {collection_id}: {current}/{total} ({percentage}%)")
                    else:
                        print(f"  Collection {collection_id}: {current} documents processed")
            
            # Status callback for simple CLI
            def status_callback(collection_id: str, status: str, missing: int = 0,
                              migrated: int = 0, total: int = 0, current_batch: int = 0,
                              state: str = "", total_batches: int = 0):
                if use_rich and console:
                    if status in ["Completed", "Synced"]:
                        console.print(f"  [bold green]✓ {collection_id}:[/bold green] [green]{status}[/green]")
                    elif status == "Failed":
                        console.print(f"  [bold red]✗ {collection_id}:[/bold red] [red]{status}[/red]")
                    elif status == "Processing":
                        if total_batches > 0:
                            console.print(f"  [yellow]⟳ {collection_id}:[/yellow] Processing batch [cyan]{current_batch + 1}/{total_batches}[/cyan]")
                        elif total > 0:
                            console.print(f"  [yellow]⟳ {collection_id}:[/yellow] [cyan]{migrated}/{total}[/cyan] documents")
                else:
                    if status in ["Completed", "Synced"]:
                        print(f"  ✅ {collection_id}: {status}")
                    elif status == "Failed":
                        print(f"  ❌ {collection_id}: {status}")
                    elif status == "Processing":
                        if total_batches > 0:
                            print(f"  🔄 {collection_id}: Processing batch {current_batch + 1}/{total_batches}")
                        elif total > 0:
                            print(f"  🔄 {collection_id}: {migrated}/{total} documents")
            
            # Determine mode and execute
            try:
                if args.migrate:
                    if use_rich and console:
                        console.print("[bold cyan]🔄 Running in MIGRATE mode - migrating all collections[/bold cyan]")
                        console.print()
                    else:
                        print("[*] Running in MIGRATE mode - migrating all collections")
                        print()
                    result = asyncio.run(
                        migration_ops.migrate_all(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            reverse=reverse,
                            progress_callback=progress_callback,
                            status_callback=status_callback
                        )
                    )
                    print()
                    if use_rich and console:
                        from rich.panel import Panel
                        from rich.table import Table
                        summary = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
                        summary.add_column("Metric", style="cyan")
                        summary.add_column("Value", style="bold white")
                        summary.add_row("Status", "[bold green]✓ Completed[/bold green]")
                        summary.add_row("Total documents migrated", f"[green]{result.get('total_documents', 0):,}[/green]")
                        summary.add_row("Successful collections", f"[green]{len(result.get('successful_collections', []))}[/green]")
                        if result.get('failed_collections'):
                            summary.add_row("Failed collections", f"[red]{result.get('failed_collections')}[/red]")
                        console.print(Panel(summary, title="[bold green]Migration Completed[/bold green]", border_style="green"))
                    else:
                        print("=" * 80)
                        print("[+] Migration completed!")
                        print(f"Total documents migrated: {result.get('total_documents', 0)}")
                        print(f"Successful collections: {len(result.get('successful_collections', []))}")
                        if result.get('failed_collections'):
                            print(f"Failed collections: {result.get('failed_collections')}")
                        print("=" * 80)
                    
                elif args.migrate_usc:
                    if use_rich and console:
                        console.print("[bold cyan]🔍 Running in MIGRATE-USC mode - migrating only missing collections[/bold cyan]")
                        console.print()
                    else:
                        print("[*] Running in MIGRATE-USC mode - migrating only missing collections")
                        print()
                    result = asyncio.run(
                        migration_ops.migrate_with_checks(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            reverse=reverse,
                            progress_callback=progress_callback,
                            status_callback=status_callback
                        )
                    )
                    print()
                    if use_rich and console:
                        from rich.panel import Panel
                        from rich.table import Table
                        summary = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
                        summary.add_column("Metric", style="cyan")
                        summary.add_column("Value", style="bold white")
                        summary.add_row("Status", "[bold green]✓ Completed[/bold green]")
                        summary.add_row("Total documents migrated", f"[green]{result.get('total_documents', 0):,}[/green]")
                        summary.add_row("Successful collections", f"[green]{len(result.get('successful_collections', []))}[/green]")
                        if result.get('failed_collections'):
                            summary.add_row("Failed collections", f"[red]{result.get('failed_collections')}[/red]")
                        console.print(Panel(summary, title="[bold green]Migration Completed[/bold green]", border_style="green"))
                    else:
                        print("=" * 80)
                        print("[+] Migration completed!")
                        print(f"Total documents migrated: {result.get('total_documents', 0)}")
                        print(f"Successful collections: {len(result.get('successful_collections', []))}")
                        if result.get('failed_collections'):
                            print(f"Failed collections: {result.get('failed_collections')}")
                        print("=" * 80)
                    
                elif args.migrate_check:
                    check_count = getattr(args, 'check_count', False)
                    if use_rich and console:
                        console.print(f"[bold cyan]✓ Running in CHECK mode - checking synchronization[/bold cyan] [dim](count: {check_count})[/dim]")
                        console.print()
                    else:
                        print(f"[*] Running in CHECK mode - checking synchronization (count: {check_count})")
                        print()
                    result = asyncio.run(
                        migration_ops.check_sync(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            check_count=check_count
                        )
                    )
                    print()
                    if use_rich and console:
                        from rich.panel import Panel
                        from rich.table import Table
                        summary = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
                        summary.add_column("Metric", style="cyan")
                        summary.add_column("Value", style="bold white")
                        summary.add_row("Status", "[bold green]✓ Check Completed[/bold green]")
                        if result.get('missing_collections'):
                            summary.add_row("Missing collections", f"[red]{result.get('missing_collections')}[/red]")
                        if result.get('collections_with_missing_points'):
                            summary.add_row("Collections with missing points", f"[yellow]{len(result.get('collections_with_missing_points', []))}[/yellow]")
                            total_missing = result.get('total_missing_points', 0)
                            if total_missing > 0:
                                summary.add_row("Total missing points", f"[red]{total_missing:,}[/red]")
                        if not result.get('missing_collections') and not result.get('collections_with_missing_points'):
                            summary.add_row("Result", "[bold green]✓ All collections are synchronized![/bold green]")
                        console.print(Panel(summary, title="[bold green]Synchronization Check Completed[/bold green]", border_style="green"))
                    else:
                        print("=" * 80)
                        print("[+] Synchronization check completed!")
                        if result.get('missing_collections'):
                            print(f"Missing collections: {result.get('missing_collections')}")
                        if result.get('collections_with_missing_points'):
                            print(f"Collections with missing points: {len(result.get('collections_with_missing_points', []))}")
                            total_missing = result.get('total_missing_points', 0)
                            if total_missing > 0:
                                print(f"Total missing points: {total_missing}")
                        if not result.get('missing_collections') and not result.get('collections_with_missing_points'):
                            print("✅ All collections are synchronized!")
                        print("=" * 80)
                
                return 0
                
            except KeyboardInterrupt:
                print()
                print("[!] Migration interrupted by user")
                return 130
            except Exception as e:
                formatter.print_error(
                    "Migration Failed",
                    f"{type(e).__name__}: {e}",
                    [
                        "Check that source and target Qdrant instances are accessible",
                        "Verify environment variables (QDRANT_URL, QDRANT_PORT, QDRANT_URL_2, QDRANT_PORT_2)",
                        "Check MySQL connection if using database",
                        "Check that all required dependencies are installed"
                    ]
                )
                import traceback
                traceback.print_exc()
                return 1
        
        # Initialize services based on operation type
        shard_ops = None
        cluster_ops = None
        mysql_service = None
        
        if not is_snapshot_op:
            # Initialize QdrantClientManager (from existing configuration) for shard operations
            print("[*] Initializing Qdrant client...")
            QdrantClientManager.initialize()
            print("[+] Qdrant client initialized")
            print()
            
            # Initialize MySQL if needed (MySQL is now the default for --save, -ml, --latest)
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
            if use_rich_output and rich_console:
                if shard_ids:
                    rich_console.print(f"[bold cyan]➡️  Moving shards[/bold cyan] [yellow]{shard_ids}[/yellow] [dim]from peer[/dim] [cyan]{args.from_peer}[/cyan] [dim]to peer[/dim] [cyan]{args.to_peer}[/cyan]")
                else:
                    rich_console.print(f"[bold cyan]➡️  Moving all shards[/bold cyan] [dim]from peer[/dim] [cyan]{args.from_peer}[/cyan] [dim]to peer[/dim] [cyan]{args.to_peer}[/cyan]")
                rich_console.print(f"   [dim]Method:[/dim] [yellow]{args.method}[/yellow]")
                rich_console.print()
            else:
                if shard_ids:
                    print(f"[>] Moving shards {shard_ids} from peer {args.from_peer} to peer {args.to_peer}")
                else:
                    print(f"[>] Moving all shards from peer {args.from_peer} to peer {args.to_peer}")
                print(f"   Method: {args.method}")
                print()
            
            # Get all shards from both peers
            if args.latest:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📋 Getting shard information from MySQL (latest)...[/cyan]")
                else:
                    print(f"📋 Getting shard information from MySQL (latest)...")
                all_peer_shards = mysql_service.get_latest_peers_as_dict()
                if use_rich_output and rich_console:
                    rich_console.print(f"[green]✓ Retrieved peer information from MySQL[/green]")
                else:
                    print(f"✓ Retrieved peer information from MySQL")
            else:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📋 Getting shard information from peers...[/cyan]")
                else:
                    print(f"📋 Getting shard information from peers...")
                all_peer_shards = cluster_ops.list_all_shards(
                    collection_name=args.collection,
                    timeout=args.timeout
                )
            if use_rich_output and rich_console:
                rich_console.print()
            else:
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
            if use_rich_output and rich_console:
                if shard_ids:
                    rich_console.print(f"[bold cyan]📄 Replicating shards[/bold cyan] [yellow]{shard_ids}[/yellow] [dim]from peer[/dim] [cyan]{args.from_peer}[/cyan] [dim]to peer[/dim] [cyan]{args.to_peer}[/cyan]")
                else:
                    rich_console.print(f"[bold cyan]📄 Replicating all shards[/bold cyan] [dim]from peer[/dim] [cyan]{args.from_peer}[/cyan] [dim]to peer[/dim] [cyan]{args.to_peer}[/cyan]")
                rich_console.print(f"   [dim]Method:[/dim] [yellow]{args.method}[/yellow]")
                rich_console.print()
            else:
                if shard_ids:
                    print(f"[>] Replicating shards {shard_ids} from peer {args.from_peer} to peer {args.to_peer}")
                else:
                    print(f"[>] Replicating all shards from peer {args.from_peer} to peer {args.to_peer}")
                print(f"   Method: {args.method}")
                print()
            
            # Get all shards from both peers
            if args.latest:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📋 Getting shard information from MySQL (latest)...[/cyan]")
                else:
                    print(f"📋 Getting shard information from MySQL (latest)...")
                all_peer_shards = mysql_service.get_latest_peers_as_dict()
                if use_rich_output and rich_console:
                    rich_console.print(f"[green]✓ Retrieved peer information from MySQL[/green]")
                else:
                    print(f"✓ Retrieved peer information from MySQL")
            else:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📋 Getting shard information from peers...[/cyan]")
                else:
                    print(f"📋 Getting shard information from peers...")
                all_peer_shards = cluster_ops.list_all_shards(
                    collection_name=args.collection,
                    timeout=args.timeout
                )
            if use_rich_output and rich_console:
                rich_console.print()
            else:
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
            
            if use_rich_output and rich_console:
                rich_console.print(f"[bold yellow]⚠️  Aborting transfer[/bold yellow] [dim]for shard[/dim] [cyan]{shard_id}[/cyan] [dim]from peer[/dim] [cyan]{args.from_peer}[/cyan] [dim]to peer[/dim] [cyan]{args.to_peer}[/cyan]")
                rich_console.print()
            else:
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
        
        # =================================================================
        # SNAPSHOT OPERATIONS
        # =================================================================
        
        elif args.snap_list:
            # Get connection info from --public-host or environment
            url, port, https, api_key = _get_snapshot_connection(args)
            
            if args.full:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📸 Listing full (cluster) snapshots...[/cyan]")
                    rich_console.print()
                else:
                    print(f"[*] Listing full (cluster) snapshots...")
                    print()
                snapshots = SnapshotService.list_cluster_snapshots(url, port, https, api_key)
            else:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📸 Listing snapshots for collection[/cyan] [yellow]'{args.collection}'[/yellow]...")
                    rich_console.print()
                else:
                    print(f"[*] Listing snapshots for collection '{args.collection}'...")
                    print()
                snapshots = SnapshotService.list_collection_snapshots(url, port, https, api_key, args.collection)
            
            if not snapshots:
                if use_rich_output and rich_console:
                    rich_console.print("[yellow]⚠ No snapshots found.[/yellow]")
                else:
                    print("No snapshots found.")
            else:
                if use_rich_output and rich_console:
                    from rich.table import Table
                    table = Table(title="Snapshots", box=box.ROUNDED, show_header=True)
                    table.add_column("Name", style="cyan", width=60)
                    table.add_column("Size", style="green", justify="right", width=15)
                    table.add_column("Created", style="yellow", width=25)
                    
                    for snap in snapshots:
                        name = snap.get("name", "Unknown")
                        size = snap.get("size", 0)
                        created = snap.get("creation_time", "N/A")
                        # Format size
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        else:
                            size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                        
                        # Format time
                        if "T" in str(created):
                            created = str(created).split(".")[0].replace("T", " ")
                        
                        table.add_row(name, size_str, str(created))
                    
                    rich_console.print(table)
                    rich_console.print(f"[green]Total: {len(snapshots)} snapshot(s)[/green]")
                else:
                    print(f"{'Name':<60} {'Size':>15} {'Created':<25}")
                    print("-" * 100)
                    for snap in snapshots:
                        name = snap.get("name", "Unknown")
                        size = snap.get("size", 0)
                        created = snap.get("creation_time", "N/A")
                        # Format size
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        else:
                            size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                        print(f"{name:<60} {size_str:>15} {str(created):<25}")
                    print()
                    print(f"Total: {len(snapshots)} snapshot(s)")
        
        elif args.snap_create:
            url, port, https, api_key = _get_snapshot_connection(args)
            
            if args.full:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📸 Creating full (cluster) snapshot...[/cyan]")
                    rich_console.print()
                else:
                    print(f"[*] Creating full (cluster) snapshot...")
                    print()
                result = SnapshotService.create_cluster_snapshot(url, port, https, api_key)
            else:
                if use_rich_output and rich_console:
                    rich_console.print(f"[cyan]📸 Creating snapshot for collection[/cyan] [yellow]'{args.collection}'[/yellow]...")
                    rich_console.print()
                else:
                    print(f"[*] Creating snapshot for collection '{args.collection}'...")
                    print()
                result = SnapshotService.create_collection_snapshot(url, port, https, api_key, args.collection)
            
            if use_rich_output and rich_console:
                from rich.panel import Panel
                from rich.table import Table
                info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Status", "[bold green]✓ Created successfully[/bold green]")
                info_table.add_row("Name", result.get('name', 'N/A'))
                size = result.get('size', 0)
                if size:
                    if size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                    info_table.add_row("Size", f"[green]{size_str}[/green]")
                rich_console.print(Panel(info_table, title="[bold green]Snapshot Created[/bold green]", border_style="green"))
            else:
                print(f"[+] Snapshot created successfully!")
                print(f"    Name: {result.get('name', 'N/A')}")
                size = result.get('size', 0)
                if size:
                    if size < 1024 * 1024:
                        print(f"    Size: {size / 1024:.1f} KB")
                    elif size < 1024 * 1024 * 1024:
                        print(f"    Size: {size / (1024 * 1024):.1f} MB")
                    else:
                        print(f"    Size: {size / (1024 * 1024 * 1024):.2f} GB")
        
        elif args.snap_delete:
            url, port, https, api_key = _get_snapshot_connection(args)
            
            if args.full:
                if use_rich_output and rich_console:
                    rich_console.print(f"[yellow]🗑️  Deleting full snapshot[/yellow] [cyan]'{args.snapshot_name}'[/cyan]...")
                    rich_console.print()
                else:
                    print(f"[*] Deleting full snapshot '{args.snapshot_name}'...")
                    print()
                SnapshotService.delete_cluster_snapshot(url, port, https, api_key, args.snapshot_name)
            else:
                if use_rich_output and rich_console:
                    rich_console.print(f"[yellow]🗑️  Deleting snapshot[/yellow] [cyan]'{args.snapshot_name}'[/cyan] [dim]from collection[/dim] [yellow]'{args.collection}'[/yellow]...")
                    rich_console.print()
                else:
                    print(f"[*] Deleting snapshot '{args.snapshot_name}' from collection '{args.collection}'...")
                    print()
                SnapshotService.delete_collection_snapshot(url, port, https, api_key, args.collection, args.snapshot_name)
            
            if use_rich_output and rich_console:
                rich_console.print(f"[bold green]✓ Snapshot '{args.snapshot_name}' deleted successfully![/bold green]")
            else:
                print(f"[+] Snapshot '{args.snapshot_name}' deleted successfully!")
        
        elif args.snap_recover:
            url, port, https, api_key = _get_snapshot_connection(args)
            
            if use_rich_output and rich_console:
                rich_console.print(f"[cyan]🔄 Recovering collection[/cyan] [yellow]'{args.collection}'[/yellow] [dim]from snapshot...[/dim]")
                from rich.table import Table
                info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                info_table.add_column("Setting", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Location", args.location)
                info_table.add_row("Priority", args.priority)
                if args.location_api_key:
                    info_table.add_row("Location API Key", "[green]Yes[/green]")
                rich_console.print(info_table)
                rich_console.print()
            else:
                print(f"[*] Recovering collection '{args.collection}' from snapshot...")
                print(f"    Location: {args.location}")
                print(f"    Priority: {args.priority}")
                if args.location_api_key:
                    print(f"    Using location API key: Yes")
                print()
            
            SnapshotService.recover_collection_snapshot(
                url, port, https, api_key,
                args.collection,
                args.location,
                priority=args.priority,
                location_api_key=args.location_api_key
            )
            
            if use_rich_output and rich_console:
                rich_console.print(f"[bold green]✓ Collection '{args.collection}' recovered successfully![/bold green]")
            else:
                print(f"[+] Collection '{args.collection}' recovered successfully!")
        
        elif args.snap_download:
            url, port, https, api_key = _get_snapshot_connection(args)
            
            output_path = args.output or args.snapshot_name
            
            if use_rich_output and rich_console:
                rich_console.print(f"[cyan]⬇️  Downloading snapshot[/cyan] [yellow]'{args.snapshot_name}'[/yellow]...")
                from rich.table import Table
                info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                info_table.add_column("Setting", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Collection", args.collection)
                info_table.add_row("Output", output_path)
                rich_console.print(info_table)
                rich_console.print()
            else:
                print(f"[*] Downloading snapshot '{args.snapshot_name}'...")
                print(f"    Collection: {args.collection}")
                print(f"    Output: {output_path}")
                print()
            
            result_path = SnapshotService.download_snapshot(
                url, port, https, api_key,
                args.collection,
                args.snapshot_name,
                output_path
            )
            
            if use_rich_output and rich_console:
                from rich.panel import Panel
                from rich.table import Table
                info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Status", "[bold green]✓ Downloaded successfully[/bold green]")
                info_table.add_row("Saved to", result_path)
                rich_console.print(Panel(info_table, title="[bold green]Snapshot Downloaded[/bold green]", border_style="green"))
            else:
                print(f"[+] Snapshot downloaded successfully!")
                print(f"    Saved to: {result_path}")
        
        # Final success message
        if use_rich_output and rich_console:
            rich_console.print()
            rich_console.print(Panel("[bold green]✓ Operation completed[/bold green]", border_style="green"))
        else:
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

