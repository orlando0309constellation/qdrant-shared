"""
Base menu class for Interactive CLI menus.
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from qdrant_distributed.cli.interactive.models import MenuAction
from qdrant_distributed.cli.interactive.ui import UIHelper
from qdrant_distributed.cli.interactive.prompts import PromptHelper
from qdrant_distributed.cli.interactive.config_manager import ConfigManager


class BaseMenu:
    """Base class for all menu handlers."""
    
    def __init__(
        self,
        console: Console,
        ui: UIHelper,
        prompts: PromptHelper,
        config_manager: ConfigManager,
        current_config,
        saved_connections: list,
        recent_collections: list
    ):
        self.console = console
        self.ui = ui
        self.prompts = prompts
        self.config_manager = config_manager
        # Store references so menus can update them
        self.current_config = current_config
        self.saved_connections = saved_connections
        self.recent_collections = recent_collections
    
    def run_with_spinner(self, message: str, func, *args, **kwargs):
        """Run a function with a spinner animation."""
        from rich.progress import Progress, SpinnerColumn, TextColumn
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            progress.add_task(description=message, total=None)
            return func(*args, **kwargs)
    
    def show_menu_header(self, title: str):
        """Show menu header with banner and connection status."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        self.ui.show_connection_status(self.current_config)
        self.console.print()
        self.console.print(Panel(f"[bold]{title}[/bold]", style="cyan"))
        self.console.print()

