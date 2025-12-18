"""
Main menu handler.
"""

from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction


class MainMenu(BaseMenu):
    """Main menu handler."""
    
    def display(self) -> MenuAction:
        """Display the main menu."""
        self.ui.clear_screen()
        self.ui.show_banner()
        self.ui.show_connection_status(self.current_config)
        
        options = [
            ("snapshots", "📸 Snapshot Management"),
            ("shards", "🔀 Shard Operations"),
            ("migration", "🔄 Migration"),
            ("cluster", "🌐 Cluster Information"),
            ("config", "⚙️  Connection Settings"),
        ]
        
        choice = self.ui.show_menu("Main Menu", options)
        
        if choice == "back":
            return MenuAction.EXIT
        elif choice == "snapshots":
            return "snapshots"
        elif choice == "shards":
            return "shards"
        elif choice == "migration":
            return "migration"
        elif choice == "cluster":
            return "cluster"
        elif choice == "config":
            return "config"
        
        return MenuAction.CONTINUE

