"""
Shard menu handler.
"""

from rich.panel import Panel
from rich.table import Table
from rich import box

from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction


class ShardMenu(BaseMenu):
    """Shard menu handler."""
    
    def display(self) -> MenuAction:
        """Display the shard operations menu."""
        while True:
            self.show_menu_header("Shard Operations")
            
            options = [
                ("list", "📋 List Shards"),
                ("move", "➡️  Move Shards"),
                ("replicate", "📄 Replicate Shards"),
                ("abort", "⛔ Abort Transfer"),
            ]
            
            choice = self.ui.show_menu("Shard Operations", options)
            
            if choice == "back":
                return MenuAction.CONTINUE
            elif choice == "list":
                self._list()
            elif choice == "move":
                self._move()
            elif choice == "replicate":
                self._replicate()
            elif choice == "abort":
                self._abort()
    
    def _list(self):
        """List shards interactively."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]List Shards[/bold]", style="cyan"))
        
        collection_name = self.prompts.prompt_collection(self.recent_collections)
        if collection_name:
            self.config_manager.add_recent_collection(self.recent_collections, collection_name)
        if not collection_name:
            self.ui.show_error("Collection name is required")
            self.ui.pause()
            return
        
        try:
            from qdrant_distributed.client.qdrant_client import QdrantClientManager
            from qdrant_distributed import ClusterOperations
            
            self.console.print()
            self.run_with_spinner("Initializing Qdrant client...", QdrantClientManager.initialize)
            
            cluster_ops = ClusterOperations()
            peer_shards = self.run_with_spinner(
                "Loading shard information...",
                cluster_ops.list_all_shards,
                collection_name=collection_name
            )
            
            if not peer_shards:
                self.ui.show_warning("No shards found")
            else:
                for peer_id, shards in peer_shards.items():
                    table = Table(title=f"Peer {peer_id}", box=box.ROUNDED)
                    table.add_column("Shard ID", style="cyan")
                    table.add_column("Local Points", style="yellow", justify="right")
                    table.add_column("State", style="green")
                    
                    for shard in shards:
                        table.add_row(
                            str(shard.shard_id),
                            f"{shard.points_count:,}",
                            shard.state
                        )
                    
                    self.console.print(table)
                    self.console.print()
                
                total_shards = sum(len(s) for s in peer_shards.values())
                self.ui.show_success(f"Found {total_shards} shard(s) across {len(peer_shards)} peer(s)")
                
        except Exception as e:
            self.ui.show_error(f"Failed to list shards: {e}")
        
        self.ui.pause()
    
    def _move(self):
        """Move shards interactively."""
        self.ui.show_info("Shard move - Use CLI: qdrant-shard -mv --from-peer X --to-peer Y")
        self.ui.pause()
    
    def _replicate(self):
        """Replicate shards interactively."""
        self.ui.show_info("Shard replicate - Use CLI: qdrant-shard -rs --from-peer X --to-peer Y")
        self.ui.pause()
    
    def _abort(self):
        """Abort shard transfer interactively."""
        self.ui.show_info("Abort transfer - Use CLI: qdrant-shard -abort --shard-id X --from-peer Y --to-peer Z")
        self.ui.pause()
