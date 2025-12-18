"""
UI helpers for Interactive CLI.
"""

import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# ASCII Art Banner
BANNER = r"""
[bold cyan]
   ____      _                 _     __  __                                   
  / __ \    | |               | |   |  \/  |                                  
 | |  | | __| |_ __ __ _ _ __ | |_  | \  / | __ _ _ __   __ _  __ _  ___ _ __ 
 | |  | |/ _` | '__/ _` | '_ \| __| | |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
 | |__| | (_| | | | (_| | | | | |_  | |  | | (_| | | | | (_| | (_| |  __/ |   
  \___\_\\__,_|_|  \__,_|_| |_|\__| |_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
                                                              __/ |          
                                                             |___/           
[/bold cyan]
[dim]Cluster Management • Snapshots • Shard Operations • Migration[/dim]
"""

MINI_BANNER = r"""[bold cyan]╔═══════════════════════════════════════╗
║       Qdrant Manager CLI v0.1.0       ║
╚═══════════════════════════════════════╝[/bold cyan]"""


class UIHelper:
    """UI helper methods for Interactive CLI."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_banner(self, mini: bool = False):
        """Display the ASCII art banner."""
        if mini:
            self.console.print(MINI_BANNER)
        else:
            self.console.print(BANNER)
    
    def show_menu(self, title: str, options: list, show_back: bool = True) -> str:
        """
        Display an interactive menu and get user choice.
        
        Args:
            title: Menu title
            options: List of (key, description) tuples
            show_back: Whether to show back/exit option
            
        Returns:
            Selected option key
        """
        self.console.print()
        self.console.print(Panel(f"[bold]{title}[/bold]", style="cyan"))
        self.console.print()
        
        # Build menu table
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Option", style="bold cyan", width=6)
        table.add_column("Description", style="white")
        
        valid_choices = []
        for i, (key, desc) in enumerate(options, 1):
            table.add_row(f"[{i}]", desc)
            valid_choices.append(str(i))
        
        if show_back:
            table.add_row("", "")  # Spacer
            table.add_row("[0]", "[dim]← Back / Exit[/dim]")
            valid_choices.append("0")
        
        self.console.print(table)
        self.console.print()
        
        # Get user input
        from rich.prompt import Prompt
        while True:
            choice = Prompt.ask("[bold cyan]Select option[/bold cyan]", default="0")
            if choice in valid_choices:
                if choice == "0":
                    return "back"
                return options[int(choice) - 1][0]
            self.console.print("[red]Invalid choice. Please try again.[/red]")
    
    def show_success(self, message: str):
        """Display a success message."""
        self.console.print(f"\n[bold green]✓ {message}[/bold green]\n")
    
    def show_error(self, message: str):
        """Display an error message."""
        self.console.print(f"\n[bold red]✗ {message}[/bold red]\n")
    
    def show_warning(self, message: str):
        """Display a warning message."""
        self.console.print(f"\n[bold yellow]⚠ {message}[/bold yellow]\n")
    
    def show_info(self, message: str):
        """Display an info message."""
        self.console.print(f"\n[bold blue]ℹ {message}[/bold blue]\n")
    
    def pause(self, message: str = "Press Enter to continue..."):
        """Pause and wait for user input."""
        self.console.print()
        from rich.prompt import Prompt
        Prompt.ask(f"[dim]{message}[/dim]", default="")
    
    def show_connection_status(self, config):
        """Display current connection status."""
        from qdrant_distributed.cli.interactive.models import ConnectionConfig
        
        name_part = f"[cyan]{config.name}[/cyan] | " if config.name else ""
        status_text = f"[bold]{name_part}{config.display_url}[/bold]"
        if config.api_key:
            status_text += " [green]🔐[/green]"
        else:
            status_text += " [yellow]⚠ No API Key[/yellow]"
        
        self.console.print(Panel(status_text, style="dim"))

