"""
Refactored Interactive CLI - Main coordinator class.
"""

from rich.console import Console

from qdrant_distributed.cli.interactive.models import ConnectionConfig, MenuAction
from qdrant_distributed.cli.interactive.ui import UIHelper
from qdrant_distributed.cli.interactive.prompts import PromptHelper
from qdrant_distributed.cli.interactive.config_manager import ConfigManager
from qdrant_distributed.cli.interactive.menus.main_menu import MainMenu
from qdrant_distributed.cli.interactive.menus.snapshot_menu import SnapshotMenu
from qdrant_distributed.cli.interactive.menus.shard_menu import ShardMenu
from qdrant_distributed.cli.interactive.menus.migration_menu import MigrationMenu
from qdrant_distributed.cli.interactive.menus.cluster_menu import ClusterMenu
from qdrant_distributed.cli.interactive.menus.config_menu import ConfigMenu

# Initialize Rich console
console = Console()


class InteractiveCLI:
    """Interactive CLI application for Qdrant management - Refactored."""
    
    def __init__(self):
        self.console = console
        self.running = True
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.ui = UIHelper(self.console)
        self.prompts = PromptHelper(self.console)
        
        # Load configurations
        self.current_config = self.config_manager.load_last_connection() or ConnectionConfig.from_env()
        self.saved_connections = self.config_manager.load_saved_connections()
        self.recent_collections = self.config_manager.load_recent_collections()
        self.saved_migrations = self.config_manager.load_saved_migrations()
    
    def run(self):
        """Run the interactive CLI main loop."""
        try:
            while self.running:
                result = self.main_menu()
                if result == MenuAction.EXIT:
                    self.running = False
        except KeyboardInterrupt:
            pass
        finally:
            self.ui.clear_screen()
            self.console.print()
            self.console.print("[bold cyan]Thank you for using Qdrant Manager![/bold cyan]")
            self.console.print("[dim]Goodbye! 👋[/dim]")
            self.console.print()
    
    def main_menu(self) -> MenuAction:
        """Display the main menu."""
        # Create menu handlers
        menu = MainMenu(
            self.console, self.ui, self.prompts, self.config_manager,
            self.current_config, self.saved_connections, self.recent_collections
        )
        
        choice = menu.display()
        
        if choice == MenuAction.EXIT or choice == MenuAction.CONTINUE:
            return choice
        
        # Route to appropriate menu
        if choice == "snapshots":
            snapshot_menu = SnapshotMenu(
                self.console, self.ui, self.prompts, self.config_manager,
                self.current_config, self.saved_connections, self.recent_collections
            )
            result = snapshot_menu.display()
            # Update collections if used
            if snapshot_menu.recent_collections != self.recent_collections:
                self.recent_collections = snapshot_menu.recent_collections
                self.config_manager.save_recent_collections(self.recent_collections)
            return result
        
        elif choice == "shards":
            shard_menu = ShardMenu(
                self.console, self.ui, self.prompts, self.config_manager,
                self.current_config, self.saved_connections, self.recent_collections
            )
            result = shard_menu.display()
            # Update collections if used
            if shard_menu.recent_collections != self.recent_collections:
                self.recent_collections = shard_menu.recent_collections
                self.config_manager.save_recent_collections(self.recent_collections)
            return result
        
        elif choice == "migration":
            migration_menu = MigrationMenu(
                self.console, self.ui, self.prompts, self.config_manager,
                self.current_config, self.saved_connections, self.recent_collections,
                saved_migrations=self.saved_migrations
            )
            result = migration_menu.display()
            # Update migrations if saved
            if migration_menu.saved_migrations != self.saved_migrations:
                self.saved_migrations = migration_menu.saved_migrations
                self.config_manager.save_migrations(self.saved_migrations)
            return result
        
        elif choice == "cluster":
            cluster_menu = ClusterMenu(
                self.console, self.ui, self.prompts, self.config_manager,
                self.current_config, self.saved_connections, self.recent_collections
            )
            return cluster_menu.display()
        
        elif choice == "config":
            config_menu = ConfigMenu(
                self.console, self.ui, self.prompts, self.config_manager,
                self.current_config, self.saved_connections, self.recent_collections
            )
            result = config_menu.display()
            # Update configs if changed
            if config_menu.current_config != self.current_config:
                self.current_config = config_menu.current_config
                self.config_manager.save_last_connection(self.current_config)
            if config_menu.saved_connections != self.saved_connections:
                self.saved_connections = config_menu.saved_connections
                self.config_manager.save_connections(self.saved_connections)
            if config_menu.recent_collections != self.recent_collections:
                self.recent_collections = config_menu.recent_collections
                self.config_manager.save_recent_collections(self.recent_collections)
            return result
        
        return MenuAction.CONTINUE


def main():
    """Entry point for interactive CLI."""
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()

