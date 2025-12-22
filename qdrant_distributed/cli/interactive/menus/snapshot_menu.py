"""
Snapshot menu handler.
"""

from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box

from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction


class SnapshotMenu(BaseMenu):
    """Snapshot menu handler."""
    
    def display(self) -> MenuAction:
        """Display the snapshot management menu."""
        while True:
            self.show_menu_header("Snapshot Management")
            
            options = [
                ("list", "📋 List Snapshots"),
                ("create", "➕ Create Snapshot"),
                ("recover", "🔄 Recover from Snapshot"),
                ("delete", "🗑️  Delete Snapshot"),
                ("download", "⬇️  Download Snapshot"),
            ]
            
            choice = self.ui.show_menu("Snapshot Management", options)
            
            if choice == "back":
                return MenuAction.CONTINUE
            elif choice == "list":
                self._list()
            elif choice == "create":
                self._create()
            elif choice == "recover":
                self._recover()
            elif choice == "delete":
                self._delete()
            elif choice == "download":
                self._download()
    
    def _list(self):
        """List snapshots interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]List Snapshots[/bold]", style="cyan"))
        self.console.print()
        
        # Ask for snapshot type
        snap_type = self.ui.show_menu("Select snapshot type", [
            ("collection", "Collection Snapshots"),
            ("full", "Full (Cluster) Snapshots"),
        ], show_back=True)
        
        if snap_type == "back":
            return
        
        # Get connection
        config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
        
        collection_name = None
        if snap_type == "collection":
            collection_name = self.prompts.prompt_collection(self.recent_collections)
            if not collection_name:
                self.ui.show_error("Collection name is required")
                self.ui.pause()
                return
        
        try:
            from qdrant_distributed.services.snapshot_service import SnapshotService
            
            if snap_type == "full":
                snapshots = self.run_with_spinner(
                    "Loading full snapshots...",
                    SnapshotService.list_cluster_snapshots,
                    config.url, config.port, config.https, config.api_key
                )
            else:
                snapshots = self.run_with_spinner(
                    f"Loading snapshots for '{collection_name}'...",
                    SnapshotService.list_collection_snapshots,
                    config.url, config.port, config.https, config.api_key, collection_name
                )
            
            if not snapshots:
                self.ui.show_warning("No snapshots found")
            else:
                table = Table(title="Snapshots", box=box.ROUNDED)
                table.add_column("#", style="dim", width=4)
                table.add_column("Name", style="cyan")
                table.add_column("Size", justify="right", style="green")
                table.add_column("Created", style="yellow")
                
                for i, snap in enumerate(snapshots, 1):
                    name = snap.get("name", "Unknown")
                    size = snap.get("size", 0)
                    created = str(snap.get("creation_time", "N/A"))
                    
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
                    if "T" in created:
                        created = created.split(".")[0].replace("T", " ")
                    
                    table.add_row(str(i), name, size_str, created)
                
                self.console.print()
                self.console.print(table)
                self.ui.show_success(f"Found {len(snapshots)} snapshot(s)")
                
        except Exception as e:
            self.ui.show_error(f"Failed to list snapshots: {e}")
        
        self.ui.pause()
    
    def _create(self):
        """Create a snapshot interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Create Snapshot[/bold]", style="cyan"))
        self.console.print()
        
        snap_type = self.ui.show_menu("Select snapshot type", [
            ("collection", "Collection Snapshot"),
            ("full", "Full (Cluster) Snapshot"),
        ], show_back=True)
        
        if snap_type == "back":
            return
        
        config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
        
        collection_name = None
        if snap_type == "collection":
            collection_name = self.prompts.prompt_collection(self.recent_collections)
            if collection_name:
                self.config_manager.add_recent_collection(self.recent_collections, collection_name)
            if not collection_name:
                self.ui.show_error("Collection name is required")
                self.ui.pause()
                return
        
        if snap_type == "full":
            confirm_msg = "Create a full cluster snapshot?"
        else:
            confirm_msg = f"Create snapshot for collection '{collection_name}'?"
        
        if not Confirm.ask(confirm_msg, default=True):
            return
        
        try:
            from qdrant_distributed.services.snapshot_service import SnapshotService
            
            if snap_type == "full":
                result = self.run_with_spinner(
                    "Creating full snapshot (this may take a while)...",
                    SnapshotService.create_cluster_snapshot,
                    config.url, config.port, config.https, config.api_key
                )
            else:
                result = self.run_with_spinner(
                    f"Creating snapshot for '{collection_name}'...",
                    SnapshotService.create_collection_snapshot,
                    config.url, config.port, config.https, config.api_key, collection_name
                )
            
            self.ui.show_success("Snapshot created successfully!")
            
            table = Table(box=box.SIMPLE)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")
            
            if isinstance(result, dict):
                table.add_row("Name", result.get("name", "N/A"))
                size = result.get("size", 0)
                if size:
                    if size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                    table.add_row("Size", size_str)
            
            self.console.print(table)
            
        except Exception as e:
            self.ui.show_error(f"Failed to create snapshot: {e}")
        
        self.ui.pause()
    
    def _recover(self):
        """Recover from a snapshot interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Recover from Snapshot[/bold]", style="cyan"))
        self.console.print()
        
        self.console.print("[bold]Step 1: Target Server Configuration[/bold]")
        self.console.print("[dim]This is the server where the collection will be recovered[/dim]")
        config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
        
        self.console.print()
        self.console.print("[bold]Step 2: Collection[/bold]")
        collection_name = self.prompts.prompt_collection(self.recent_collections, "Collection name to recover")
        if collection_name:
            self.config_manager.add_recent_collection(self.recent_collections, collection_name)
        if not collection_name:
            self.ui.show_error("Collection name is required")
            self.ui.pause()
            return
        
        self.console.print()
        self.console.print("[bold]Step 3: Snapshot Location[/bold]")
        self.console.print("[dim]Enter the URL or path to the snapshot file[/dim]")
        self.console.print()
        
        autofill = Confirm.ask("Auto-fill location from snapshot list?", default=True)
        
        location = None
        source_api_key = None
        
        if autofill:
            self.console.print()
            self.console.print("[bold]Source Server (where snapshot exists):[/bold]")
            self.console.print("[dim]Enter full URL (e.g., https://source-server:6333) or just hostname[/dim]")
            self.console.print()
            
            source_input = Prompt.ask("Source server", default=config.display_url)
            source_url, source_port, source_https = self.prompts.parse_url(source_input)
            self.console.print(f"[green]✓ Parsed:[/green] host={source_url}, port={source_port}, https={source_https}")
            
            use_same_key = Confirm.ask("Use same API key as target?", default=True)
            if use_same_key:
                source_api_key = config.api_key
            else:
                source_api_key = Prompt.ask("Source server API key", password=True, default="")
            
            try:
                from qdrant_distributed.services.snapshot_service import SnapshotService
                
                snapshots = self.run_with_spinner(
                    "Loading snapshots from source...",
                    SnapshotService.list_collection_snapshots,
                    source_url, source_port, source_https, source_api_key, collection_name
                )
                
                if not snapshots:
                    self.ui.show_warning("No snapshots found on source server")
                    location = Prompt.ask("Enter snapshot location manually")
                else:
                    self.console.print()
                    table = Table(title="Available Snapshots", box=box.ROUNDED)
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Name", style="cyan")
                    table.add_column("Size", justify="right")
                    
                    for i, snap in enumerate(snapshots, 1):
                        name = snap.get("name", "Unknown")
                        size = snap.get("size", 0)
                        if size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        else:
                            size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                        table.add_row(str(i), name, size_str)
                    
                    self.console.print(table)
                    self.console.print()
                    
                    choice = IntPrompt.ask("Select snapshot number", default=1)
                    if 1 <= choice <= len(snapshots):
                        selected = snapshots[choice - 1]
                        snap_name = selected.get("name")
                        scheme = "https" if source_https else "http"
                        location = f"{scheme}://{source_url}:{source_port}/collections/{collection_name}/snapshots/{snap_name}"
                        self.console.print()
                        self.console.print(f"[green]Selected:[/green] {snap_name}")
                        self.console.print(f"[dim]URL: {location}[/dim]")
                    else:
                        self.ui.show_error("Invalid selection")
                        self.ui.pause()
                        return
                        
            except Exception as e:
                self.ui.show_error(f"Failed to list snapshots: {e}")
                location = Prompt.ask("Enter snapshot location manually")
        else:
            location = Prompt.ask("Snapshot location (URL or path)")
            if location and (location.startswith("http://") or location.startswith("https://")):
                if Confirm.ask("Does the source URL require authentication?", default=False):
                    source_api_key = Prompt.ask("Source server API key", password=True)
        
        if not location:
            self.ui.show_error("Snapshot location is required")
            self.ui.pause()
            return
        
        self.console.print()
        self.console.print("[bold]Step 4: Recovery Options[/bold]")
        self.console.print()
        self.console.print("[dim]Priority options (for distributed clusters):[/dim]")
        self.console.print("  • [cyan]snapshot[/cyan] - Restore from file, other nodes sync from this")
        self.console.print("  • [cyan]replica[/cyan]  - Prefer existing healthy replicas")
        self.console.print()
        
        priority = Prompt.ask("Recovery priority", choices=["snapshot", "replica"], default="snapshot")
        
        self.console.print()
        self.console.print(Panel("[bold yellow]⚠️  Recovery Summary[/bold yellow]"))
        
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("", style="cyan")
        summary.add_column("")
        summary.add_row("Target Server", config.display_url)
        summary.add_row("Collection", collection_name)
        summary.add_row("Location", location[:60] + "..." if len(location) > 60 else location)
        summary.add_row("Priority", priority)
        summary.add_row("Source Auth", "Yes" if source_api_key else "No")
        
        self.console.print(summary)
        self.console.print()
        
        if not Confirm.ask("[bold red]Proceed with recovery?[/bold red]", default=False):
            self.ui.show_info("Recovery cancelled")
            self.ui.pause()
            return
        
        try:
            from qdrant_distributed.services.snapshot_service import SnapshotService
            
            self.run_with_spinner(
                "Recovering collection (this may take a while)...",
                SnapshotService.recover_collection_snapshot,
                config.url, config.port, config.https, config.api_key,
                collection_name, location,
                priority=priority,
                location_api_key=source_api_key
            )
            
            self.ui.show_success(f"Collection '{collection_name}' recovered successfully!")
            
        except Exception as e:
            self.ui.show_error(f"Recovery failed: {e}")
        
        self.ui.pause()
    
    def _delete(self):
        """Delete a snapshot interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Delete Snapshot[/bold]", style="cyan"))
        self.console.print()
        
        snap_type = self.ui.show_menu("Select snapshot type", [
            ("collection", "Collection Snapshot"),
            ("full", "Full (Cluster) Snapshot"),
        ], show_back=True)
        
        if snap_type == "back":
            return
        
        config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
        
        collection_name = None
        if snap_type == "collection":
            collection_name = self.prompts.prompt_collection(self.recent_collections)
            if collection_name:
                self.config_manager.add_recent_collection(self.recent_collections, collection_name)
            if not collection_name:
                self.ui.show_error("Collection name is required")
                self.ui.pause()
                return
        
        try:
            from qdrant_distributed.services.snapshot_service import SnapshotService
            
            if snap_type == "full":
                snapshots = self.run_with_spinner(
                    "Loading snapshots...",
                    SnapshotService.list_cluster_snapshots,
                    config.url, config.port, config.https, config.api_key
                )
            else:
                snapshots = self.run_with_spinner(
                    "Loading snapshots...",
                    SnapshotService.list_collection_snapshots,
                    config.url, config.port, config.https, config.api_key, collection_name
                )
            
            if not snapshots:
                self.ui.show_warning("No snapshots found")
                self.ui.pause()
                return
            
            table = Table(title="Select Snapshot to Delete", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style="cyan")
            table.add_column("Size", justify="right")
            
            for i, snap in enumerate(snapshots, 1):
                name = snap.get("name", "Unknown")
                size = snap.get("size", 0)
                if size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                table.add_row(str(i), name, size_str)
            
            self.console.print(table)
            self.console.print()
            
            choice = IntPrompt.ask("Select snapshot number (0 to cancel)", default=0)
            if choice == 0:
                return
            
            if 1 <= choice <= len(snapshots):
                selected = snapshots[choice - 1]
                snap_name = selected.get("name")
                
                if not Confirm.ask(f"[bold red]Delete snapshot '{snap_name}'? This cannot be undone![/bold red]", default=False):
                    return
                
                if snap_type == "full":
                    self.run_with_spinner(
                        "Deleting snapshot...",
                        SnapshotService.delete_cluster_snapshot,
                        config.url, config.port, config.https, config.api_key, snap_name
                    )
                else:
                    self.run_with_spinner(
                        "Deleting snapshot...",
                        SnapshotService.delete_collection_snapshot,
                        config.url, config.port, config.https, config.api_key, collection_name, snap_name
                    )
                
                self.ui.show_success(f"Snapshot '{snap_name}' deleted successfully!")
            else:
                self.ui.show_error("Invalid selection")
                
        except Exception as e:
            self.ui.show_error(f"Failed to delete snapshot: {e}")
        
        self.ui.pause()
    
    def _download(self):
        """Download a snapshot interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Download Snapshot[/bold]", style="cyan"))
        self.console.print()
        
        config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
        
        collection_name = self.prompts.prompt_collection(self.recent_collections)
        if collection_name:
            self.config_manager.add_recent_collection(self.recent_collections, collection_name)
        if not collection_name:
            self.ui.show_error("Collection name is required")
            self.ui.pause()
            return
        
        try:
            from qdrant_distributed.services.snapshot_service import SnapshotService
            
            snapshots = self.run_with_spinner(
                "Loading snapshots...",
                SnapshotService.list_collection_snapshots,
                config.url, config.port, config.https, config.api_key, collection_name
            )
            
            if not snapshots:
                self.ui.show_warning("No snapshots found")
                self.ui.pause()
                return
            
            table = Table(title="Select Snapshot to Download", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style="cyan")
            table.add_column("Size", justify="right")
            
            for i, snap in enumerate(snapshots, 1):
                name = snap.get("name", "Unknown")
                size = snap.get("size", 0)
                if size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                table.add_row(str(i), name, size_str)
            
            self.console.print(table)
            self.console.print()
            
            choice = IntPrompt.ask("Select snapshot number (0 to cancel)", default=0)
            if choice == 0:
                return
            
            if 1 <= choice <= len(snapshots):
                selected = snapshots[choice - 1]
                snap_name = selected.get("name")
                
                default_output = snap_name
                output_path = Prompt.ask("Output file path", default=default_output)
                
                if not Confirm.ask(f"Download '{snap_name}' to '{output_path}'?", default=True):
                    return
                
                result = self.run_with_spinner(
                    "Downloading snapshot (this may take a while)...",
                    SnapshotService.download_snapshot,
                    config.url, config.port, config.https, config.api_key,
                    collection_name, snap_name, output_path
                )
                
                self.ui.show_success(f"Snapshot downloaded to: {result}")
            else:
                self.ui.show_error("Invalid selection")
                
        except Exception as e:
            self.ui.show_error(f"Failed to download snapshot: {e}")
        
        self.ui.pause()
