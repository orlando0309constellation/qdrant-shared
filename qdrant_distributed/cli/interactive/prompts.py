"""
Prompt helpers for user input.
"""

from typing import Optional, Dict, Any, Tuple
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.console import Console

from qdrant_distributed.cli.interactive.models import ConnectionConfig


class PromptHelper:
    """Helper methods for prompting user input."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def parse_url(self, url_string: str) -> Tuple[str, str, bool]:
        """
        Parse a URL string into components.
        
        Supports formats:
            - https://host:port
            - http://host:port
            - host:port
            - host
            
        Returns:
            Tuple of (host, port, https)
        """
        url_string = url_string.strip()
        https = False
        host = url_string
        port = "6333"
        
        # Check for scheme
        if url_string.startswith("https://"):
            https = True
            url_string = url_string[8:]  # Remove "https://"
        elif url_string.startswith("http://"):
            https = False
            url_string = url_string[7:]  # Remove "http://"
        
        # Remove any trailing path
        url_string = url_string.split("/")[0]
        
        # Parse host:port
        if ":" in url_string:
            parts = url_string.split(":")
            host = parts[0]
            port = parts[1]
        else:
            host = url_string
            port = "443" if https else "6333"
        
        return host, port, https
    
    def prompt_connection(self, current_config: ConnectionConfig, saved_connections: list) -> ConnectionConfig:
        """Interactively prompt for connection configuration."""
        self.console.print()
        self.console.print(Panel("[bold]Configure Connection[/bold]", style="cyan"))
        self.console.print()
        
        # Show current connection
        self.console.print(f"[bold]Current:[/bold] {current_config.display_name}")
        if current_config.api_key:
            self.console.print("[green]  🔐 Authenticated[/green]")
        self.console.print()
        
        # Build options
        options = [("current", f"Use current: {current_config.display_url}")]
        
        # Add saved connections
        if saved_connections:
            for i, conn in enumerate(saved_connections):
                if conn.url != current_config.url or conn.port != current_config.port:
                    name = conn.name or f"{conn.url}:{conn.port}"
                    options.append((f"saved_{i}", f"📌 {name}"))
        
        # Add option to enter new
        options.append(("new", "➕ Enter new connection"))
        
        from qdrant_distributed.cli.interactive.ui import UIHelper
        ui = UIHelper(self.console)
        choice = ui.show_menu("Select Connection", options, show_back=True)
        
        if choice == "back":
            return current_config
        elif choice == "current":
            return current_config
        elif choice.startswith("saved_"):
            idx = int(choice.split("_")[1])
            return saved_connections[idx]
        elif choice == "new":
            return self._prompt_new_connection(current_config)
        
        return current_config
    
    def _prompt_new_connection(self, default_config: ConnectionConfig) -> ConnectionConfig:
        """Prompt for a new connection configuration."""
        self.console.print()
        self.console.print("[dim]Enter a full URL (e.g., https://qdrant.example.com:6333)[/dim]")
        self.console.print("[dim]Or just press Enter to configure host/port separately[/dim]")
        self.console.print()
        
        full_url = Prompt.ask("Server URL", default="")
        
        if full_url:
            # Parse the URL
            url, port, https = self.parse_url(full_url)
            self.console.print(f"[green]✓ Parsed:[/green] host={url}, port={port}, https={https}")
        else:
            # Get individual fields
            url = Prompt.ask("Qdrant Host", default=default_config.url)
            port = Prompt.ask("Port", default=default_config.port)
            https = Confirm.ask("Use HTTPS?", default=default_config.https)
        
        # API Key
        change_key = Confirm.ask("Set API Key?", default=bool(default_config.api_key))
        api_key = None
        if change_key:
            api_key = Prompt.ask("API Key", password=True)
        
        # Optional friendly name
        name = Prompt.ask("Connection name (optional)", default="")
        
        return ConnectionConfig(url=url, port=port, https=https, api_key=api_key, name=name or None)
    
    def prompt_collection(self, recent_collections: list, prompt_text: str = "Collection name") -> str:
        """Prompt for a collection name with recent suggestions."""
        self.console.print()
        
        # Show recent collections if available
        if recent_collections:
            self.console.print("[dim]Recent collections:[/dim]")
            for i, coll in enumerate(recent_collections[:5], 1):
                self.console.print(f"  [{i}] {coll}")
            self.console.print(f"  [0] Enter manually")
            self.console.print()
            
            choice = Prompt.ask("Select or enter collection name", default="1")
            
            # Check if it's a number selection
            if choice.isdigit():
                idx = int(choice)
                if idx == 0:
                    collection = Prompt.ask(prompt_text)
                elif 1 <= idx <= len(recent_collections[:5]):
                    collection = recent_collections[idx - 1]
                else:
                    collection = choice  # Treat as collection name
            else:
                collection = choice
        else:
            collection = Prompt.ask(prompt_text)
        
        return collection
    
    def prompt_qdrant_config(self, title: str, default_config: Optional[ConnectionConfig] = None) -> Dict[str, Any]:
        """Prompt for Qdrant configuration."""
        self.console.print()
        self.console.print(Panel(f"[bold]{title}[/bold]", style="cyan"))
        self.console.print()
        
        if default_config:
            self.console.print(f"[dim]Current: {default_config.display_url}[/dim]")
            use_current = Confirm.ask("Use current connection?", default=True)
            if use_current:
                return {
                    'url': default_config.url,
                    'port': default_config.port,
                    'api_key': default_config.api_key,
                    'https': default_config.https
                }
        
        # Prompt for URL
        self.console.print()
        self.console.print("[dim]Enter a full URL (e.g., https://qdrant.example.com:6333)[/dim]")
        self.console.print("[dim]Or just press Enter to configure host/port separately[/dim]")
        self.console.print()
        
        full_url = Prompt.ask("Server URL", default="")
        
        if full_url:
            url, port_str, https = self.parse_url(full_url)
            port = int(port_str)
            self.console.print(f"[green]✓ Parsed:[/green] host={url}, port={port}, https={https}")
        else:
            url = Prompt.ask("Qdrant Host", default=default_config.url if default_config else "localhost")
            port_str = Prompt.ask("Port", default=str(default_config.port) if default_config else "6333")
            port = int(port_str)
            https = Confirm.ask("Use HTTPS?", default=default_config.https if default_config else True)
        
        # API Key
        api_key = None
        if default_config and default_config.api_key:
            use_existing = Confirm.ask("Use existing API key?", default=True)
            if use_existing:
                api_key = default_config.api_key
            else:
                set_key = Confirm.ask("Set API Key?", default=False)
                if set_key:
                    api_key = Prompt.ask("API Key", password=True)
        else:
            set_key = Confirm.ask("Set API Key?", default=False)
            if set_key:
                api_key = Prompt.ask("API Key", password=True)
        
        return {
            'url': url,
            'port': port,
            'api_key': api_key,
            'https': https
        }
    
    def prompt_mysql_config(self) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Prompt for MySQL configuration, returns (config_dict, use_default)."""
        self.console.print()
        self.console.print(Panel("[bold]MySQL Configuration[/bold]", style="cyan"))
        self.console.print()
        
        use_default = Confirm.ask("Use default MySQL configuration?", default=True)
        
        if use_default:
            return None, True
        
        # Custom MySQL config
        try:
            from qdrant_distributed.config import get_mysql_host, get_mysql_port, get_mysql_user, get_mysql_password, get_mysql_database
            
            host = Prompt.ask("MySQL Host", default=get_mysql_host())
            port_str = Prompt.ask("MySQL Port", default=str(get_mysql_port()))
            port = int(port_str)
            user = Prompt.ask("MySQL User", default=get_mysql_user())
            password = Prompt.ask("MySQL Password", password=True, default=get_mysql_password())
            database = Prompt.ask("MySQL Database", default=get_mysql_database())
            
            return {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'database': database
            }, False
        except Exception:
            self.console.print("[yellow]⚠ Could not load default MySQL config. Please enter manually.[/yellow]")
            host = Prompt.ask("MySQL Host", default="localhost")
            port_str = Prompt.ask("MySQL Port", default="3306")
            port = int(port_str)
            user = Prompt.ask("MySQL User", default="root")
            password = Prompt.ask("MySQL Password", password=True, default="")
            database = Prompt.ask("MySQL Database", default="qdrant")
            
            return {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'database': database
            }, False

