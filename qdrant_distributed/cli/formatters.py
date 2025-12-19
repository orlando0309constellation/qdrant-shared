"""
Output formatters for CLI display.
"""

from typing import Dict, List, Any

# Try to import Rich for colored output, fallback to plain text
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


class ResultFormatter:
    """Formatter for CLI output display."""
    
    def __init__(self):
        """Initialize formatter with Rich console if available."""
        if _RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
    
    def print_header(self, title: str, width: int = 80) -> None:
        """Print a formatted header with colors."""
        if self.console:
            self.console.print(Panel(title, style="bold cyan", border_style="cyan"))
        else:
            print("=" * width)
            print(title)
            print("=" * width)
    
    def print_operation_result(self, result: Dict[str, Any]) -> None:
        """
        Format and print operation result.
        
        Args:
            result: Operation result dictionary
        """
        if self.console:
            self.console.print(Panel("[bold green]✓ Operation completed successfully![/bold green]", style="green"))
            table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Status", str(result.get('status', 'N/A')))
            table.add_row("Result", str(result.get('result', 'N/A')))
            table.add_row("Time", f"{result.get('time', 0):.3f}s")
            self.console.print(table)
            
            if result.get('usage'):
                self.console.print("\n[bold yellow]Resource Usage:[/bold yellow]")
                usage = result.get('usage')
                if isinstance(usage, dict):
                    usage_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                    usage_table.add_column("Metric", style="cyan")
                    usage_table.add_column("Value", style="white")
                    for key, value in usage.items():
                        usage_table.add_row(key, str(value))
                    self.console.print(usage_table)
                else:
                    self.console.print(f"  {usage}")
        else:
            self.print_header("[+] Operation completed successfully!")
            print(f"Status: {result.get('status')}")
            print(f"Result: {result.get('result')}")
            print(f"Time: {result.get('time', 0):.3f}s")
            
            if result.get('usage'):
                print("\n[*] Resource Usage:")
                usage = result.get('usage')
                if isinstance(usage, dict):
                    for key, value in usage.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {usage}")
    
    def print_shard_list(self, peer_shards: Dict[int, List[Any]], peer_uris: Dict[int, str] = None) -> None:
        """
        Format and print shard list.
        
        Args:
            peer_shards: Dictionary of peer IDs to shard lists
            peer_uris: Optional dictionary mapping peer IDs to URIs
        """
        if self.console:
            self.console.print(Panel("[bold green]✓ Successfully retrieved shard information from all peers![/bold green]", style="green"))
            self.console.print()
            
            if not peer_shards:
                self.console.print("[yellow]⚠ No peers found or no shard information available[/yellow]")
                return
            
            total_shards = 0
            total_points = 0
            
            for peer_id, shards in sorted(peer_shards.items()):
                uri = peer_uris.get(peer_id, "") if peer_uris else ""
                peer_title = f"Peer {peer_id}" + (f" ({uri})" if uri else "")
                self.console.print(f"[bold cyan]📡 {peer_title}[/bold cyan]")
                
                if not shards:
                    self.console.print("  [dim]No local shards[/dim]")
                else:
                    shard_table = Table(show_header=True, box=box.ROUNDED, padding=(0, 2))
                    shard_table.add_column("Shard ID", style="cyan", justify="right")
                    shard_table.add_column("Points", style="yellow", justify="right")
                    shard_table.add_column("State", style="green")
                    
                    for shard in shards:
                        shard_id = shard.shard_id
                        points_count = shard.points_count
                        state = shard.state.value
                        total_shards += 1
                        total_points += points_count
                        
                        shard_table.add_row(str(shard_id), f"{points_count:,}", state)
                    
                    self.console.print(shard_table)
                
                self.console.print()
            
            # Summary
            summary_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="bold white")
            summary_table.add_row("Total Peers", str(len(peer_shards)))
            summary_table.add_row("Total Local Shards", str(total_shards))
            summary_table.add_row("Total Local Points", f"{total_points:,}")
            self.console.print(summary_table)
        else:
            self.print_header("[+] Successfully retrieved shard information from all peers!")
            print()
            
            if not peer_shards:
                print("[!] No peers found or no shard information available")
                return
            
            total_shards = 0
            total_points = 0
            
            for peer_id, shards in sorted(peer_shards.items()):
                uri = peer_uris.get(peer_id, "") if peer_uris else ""
                if uri:
                    print(f"[*] Peer {peer_id} ({uri}):")
                else:
                    print(f"[*] Peer {peer_id}:")
                print(f"   {'='*70}")
                
                if not shards:
                    print("   No local shards")
                else:
                    for shard in shards:
                        shard_id = shard.shard_id
                        points_count = shard.points_count
                        state = shard.state.value
                        total_shards += 1
                        total_points += points_count
                        
                        print(f"   - Shard {shard_id}")
                        print(f"     - Points: {points_count:,}")
                        print(f"     - State: {state}")
                
                print()
            
            print("=" * 80)
            print(f"[*] Summary:")
            print(f"   Total Peers: {len(peer_shards)}")
            print(f"   Total Local Shards: {total_shards}")
            print(f"   Total Local Points: {total_points:,}")
            print("=" * 80)
    
    def print_error(self, error_type: str, message: str, suggestions: List[str] = None) -> None:
        """
        Format and print error message.
        
        Args:
            error_type: Type of error
            message: Error message
            suggestions: Optional list of suggestions
        """
        if self.console:
            self.console.print(Panel(f"[bold red]❌ {error_type}[/bold red]\n\n[red]{message}[/red]", 
                                    style="red", border_style="red"))
            if suggestions:
                self.console.print("\n[bold yellow]Suggestions:[/bold yellow]")
                for suggestion in suggestions:
                    self.console.print(f"  [dim]•[/dim] {suggestion}")
        else:
            print("=" * 80)
            print(f"[!] {error_type}")
            print("=" * 80)
            print(f"Error: {message}")
            
            if suggestions:
                print("\nSuggestions:")
                for suggestion in suggestions:
                    print(f"  - {suggestion}")

