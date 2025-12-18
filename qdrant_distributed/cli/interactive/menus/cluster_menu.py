"""
Cluster menu handler.
"""

from rich.panel import Panel
from rich.table import Table
from rich import box

from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction


class ClusterMenu(BaseMenu):
    """Cluster menu handler."""
    
    def display(self) -> MenuAction:
        """Display the cluster information menu."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Cluster Information[/bold]", style="cyan"))
        self.console.print()
        
        try:
            from qdrant_distributed.client.qdrant_client import QdrantClientManager
            from qdrant_distributed.client import ClusterClient
            
            self.run_with_spinner("Initializing...", QdrantClientManager.initialize)
            
            cluster_client = ClusterClient()
            peers_dict, consensus = self.run_with_spinner(
                "Loading cluster info...",
                cluster_client.get_peers,
                timeout=30
            )
            
            # Show peers
            table = Table(title="Cluster Peers", box=box.ROUNDED)
            table.add_column("Peer ID", style="cyan")
            table.add_column("URI", style="white")
            
            for peer_id, peer_data in peers_dict.items():
                uri = peer_data.get("uri", "N/A")
                table.add_row(str(peer_id), uri)
            
            self.console.print(table)
            self.ui.show_success(f"Cluster has {len(peers_dict)} peer(s)")
            
        except Exception as e:
            self.ui.show_error(f"Failed to get cluster info: {e}")
        
        self.ui.pause()
        return MenuAction.CONTINUE
