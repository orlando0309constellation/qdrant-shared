"""
Configuration menu handler.
"""

from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box

from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction, ConnectionConfig
from qdrant_distributed.services.config_service import ConfigService


class ConfigMenu(BaseMenu):
    """Configuration menu handler."""
    
    def display(self) -> MenuAction:
        """Display the configuration menu."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.console.print(Panel("[bold]Connection Settings[/bold]", style="cyan"))
        self.console.print()
        
        # Show current config
        table = Table(box=box.SIMPLE, show_header=False, title="Current Connection")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        table.add_row("Name", self.current_config.name or "(unnamed)")
        table.add_row("URL", self.current_config.url)
        table.add_row("Port", self.current_config.port)
        table.add_row("HTTPS", str(self.current_config.https))
        table.add_row("API Key", "***" if self.current_config.api_key else "(not set)")
        
        self.console.print(table)
        self.console.print()
        
        # Show saved connections summary
        if self.saved_connections:
            self.console.print(f"[dim]📌 {len(self.saved_connections)} saved connection(s)[/dim]")
        self.console.print()
        
        # Show data location
        db_path = ConfigService.get_db_path()
        self.console.print(f"[dim]📁 Config stored at: {db_path}[/dim]")
        self.console.print()
        
        options = [
            ("switch", "🔄 Switch Connection"),
            ("new", "➕ Add New Connection"),
            ("manage", "📋 Manage Saved Connections"),
            ("import", "📥 Import from GUI Settings"),
            ("clear", "🗑️  Clear Recent Collections"),
            ("export", "📤 Export Settings"),
        ]
        
        choice = self.ui.show_menu("Configuration", options)
        
        if choice == "back":
            return MenuAction.CONTINUE
        elif choice == "switch":
            new_config = self.prompts.prompt_connection(self.current_config, self.saved_connections)
            self.current_config = new_config
            self.config_manager.save_last_connection(new_config)
            self.ui.show_success("Connection updated!")
        elif choice == "new":
            new_config = self.prompts._prompt_new_connection(self.current_config)
            self.config_manager.add_saved_connection(self.saved_connections, new_config)
            if Confirm.ask("Use as current connection?", default=True):
                self.current_config = new_config
                self.config_manager.save_last_connection(new_config)
        elif choice == "manage":
            self._manage_saved_connections()
        elif choice == "import":
            self._import_gui_settings()
        elif choice == "clear":
            if Confirm.ask("Clear recent collections history?", default=False):
                self.recent_collections = []
                self.config_manager.save_recent_collections(self.recent_collections)
                self.ui.show_success("Recent collections cleared!")
        elif choice == "export":
            self._export_settings()
        
        self.ui.pause()
        return MenuAction.CONTINUE
    
    def _manage_saved_connections(self):
        """Manage saved connections."""
        self.console.print()
        
        if not self.saved_connections:
            self.console.print("[yellow]No saved connections yet.[/yellow]")
            self.console.print("[dim]Use 'Add New Connection' to save your first connection.[/dim]")
            return
        
        # Show saved connections
        table = Table(box=box.ROUNDED, title="Saved Connections")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Name", style="bold")
        table.add_column("URL")
        table.add_column("Auth", width=6)
        
        for i, conn in enumerate(self.saved_connections, 1):
            auth = "🔐" if conn.api_key else "❌"
            table.add_row(
                str(i),
                conn.name or "(unnamed)",
                conn.display_url,
                auth
            )
        
        self.console.print(table)
        self.console.print()
        
        options = [
            ("delete", "🗑️  Delete a connection"),
            ("rename", "✏️  Rename a connection"),
        ]
        
        choice = self.ui.show_menu("Manage", options)
        
        if choice == "delete":
            idx = IntPrompt.ask("Enter connection number to delete", default=1)
            if 1 <= idx <= len(self.saved_connections):
                deleted = self.saved_connections.pop(idx - 1)
                self.config_manager.save_connections(self.saved_connections)
                self.ui.show_success(f"Deleted: {deleted.display_url}")
            else:
                self.ui.show_error("Invalid selection")
        elif choice == "rename":
            idx = IntPrompt.ask("Enter connection number to rename", default=1)
            if 1 <= idx <= len(self.saved_connections):
                new_name = Prompt.ask("Enter new name")
                self.saved_connections[idx - 1].name = new_name
                self.config_manager.save_connections(self.saved_connections)
                self.ui.show_success(f"Renamed to: {new_name}")
            else:
                self.ui.show_error("Invalid selection")
    
    def _import_gui_settings(self):
        """Import snapshot URLs from GUI settings."""
        self.console.print()
        self.console.print("[bold]Import from GUI Settings[/bold]")
        self.console.print("[dim]This will import snapshot URLs saved in the GUI[/dim]")
        self.console.print()
        
        # Load snapshot URLs from ConfigService (shared with GUI)
        snapshot_urls = ConfigService.get_snapshot_urls()
        
        if not snapshot_urls:
            self.ui.show_warning("No snapshot URLs found in GUI settings")
            self.console.print("[dim]Tip: Add URLs in the GUI's Snapshot Management dialog[/dim]")
            return
        
        # Show found URLs
        table = Table(box=box.ROUNDED, title="Found URLs in GUI Settings")
        table.add_column("#", style="cyan", width=4)
        table.add_column("URL")
        table.add_column("Port", width=8)
        table.add_column("HTTPS", width=6)
        
        for i, url_config in enumerate(snapshot_urls, 1):
            table.add_row(
                str(i),
                url_config.get("url", ""),
                url_config.get("port", ""),
                "✓" if url_config.get("https") else "✗"
            )
        
        self.console.print(table)
        self.console.print()
        
        if Confirm.ask("Import these as saved connections?", default=True):
            imported = 0
            for url_config in snapshot_urls:
                config = ConnectionConfig(
                    url=url_config.get("url", "localhost"),
                    port=url_config.get("port", "6333"),
                    https=url_config.get("https", False),
                    name=f"GUI Import: {url_config.get('url', 'unknown')}"
                )
                self.config_manager.add_saved_connection(self.saved_connections, config)
                imported += 1
            
            self.ui.show_success(f"Imported {imported} connection(s)!")
    
    def _export_settings(self):
        """Export current settings info."""
        self.console.print()
        self.console.print("[bold]Settings Export[/bold]")
        self.console.print()
        
        # Show summary
        table = Table(box=box.SIMPLE, title="Current Settings Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        
        table.add_row("Saved Connections", str(len(self.saved_connections)))
        table.add_row("Recent Collections", str(len(self.recent_collections)))
        table.add_row("Config File", ConfigService.get_db_path())
        
        self.console.print(table)
        self.console.print()
        
        # Show all stored keys
        if Confirm.ask("Show all stored configuration keys?", default=False):
            all_config = ConfigService.get_all()
            self.console.print()
            for key, value in all_config.items():
                # Truncate long values
                display_value = value[:50] + "..." if len(value) > 50 else value
                self.console.print(f"  [cyan]{key}[/cyan]: {display_value}")
