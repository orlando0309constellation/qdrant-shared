"""
Migration execution logic.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from rich.panel import Panel
from rich.prompt import Confirm

from qdrant_distributed.cli.interactive.models import MigrationConfig
from qdrant_distributed.cli.interactive.ui import UIHelper


class MigrationExecutor:
    """Handles migration execution."""
    
    def __init__(self, console, ui: UIHelper):
        self.console = console
        self.ui = ui
    
    def execute(
        self,
        mode: str,
        mig_config: MigrationConfig,
        saved_migrations: list,
        config_manager
    ):
        """Execute migration operation."""
        mode_names = {
            "migrate": "Migrate All Collections",
            "migrate-usc": "Migrate Missing Only",
            "check": "Check Synchronization"
        }
        
        self.console.print(Panel(f"[bold]{mode_names.get(mode, 'Migration')}[/bold]", style="cyan"))
        self.console.print()
        
        try:
            # Display full summary/resume
            self.console.print()
            self.console.print(Panel("[bold]Migration Resume - Review Before Launch[/bold]", style="yellow"))
            self.console.print()
            from qdrant_distributed.cli.interactive.migration.config_manager import MigrationConfigManager
            from qdrant_distributed.cli.interactive.prompts import PromptHelper
            temp_config_mgr = MigrationConfigManager(
                self.console, PromptHelper(self.console), None, []
            )
            temp_config_mgr.display_summary(mig_config)
            self.console.print()
            self.console.print(f"[bold]Mode:[/bold] {mode_names.get(mode, mode)}")
            self.console.print()
            
            # Allow final editing
            if Confirm.ask("Edit configuration before launch?", default=False):
                # Re-create config manager with proper dependencies
                from qdrant_distributed.cli.interactive.prompts import PromptHelper
                prompts = PromptHelper(self.console)
                config_mgr = MigrationConfigManager(
                    self.console, prompts, None, saved_migrations
                )
                mig_config = config_mgr.edit(mig_config, mode)
                self.console.print()
                config_mgr.display_summary(mig_config)
                self.console.print()
            
            # Confirm and save
            if not Confirm.ask("[bold yellow]Launch migration?[/bold yellow]", default=True):
                self.ui.show_warning("Migration cancelled")
                self.ui.pause()
                return
            
            # Save configuration
            config_manager.add_saved_migration(saved_migrations, mig_config)
            self.ui.show_success(f"Configuration '{mig_config.name}' saved!")
            self.console.print()
            
            # Get configs from MigrationConfig
            source_config = mig_config.get_source_config()
            target_config = mig_config.get_target_config()
            mysql_config = mig_config.get_mysql_config()
            reverse = mig_config.reverse
            
            # Execute migration
            from qdrant_distributed.operations.migration_operations import MigrationOperations
            from qdrant_distributed.services.migration_service import add_log_callback
            
            migration_ops = MigrationOperations()
            
            # Track elapsed time and collections
            start_time = datetime.now(timezone.utc)
            collection_start_times = {}
            processed_collections = 0
            total_collections = 0
            current_collection = None
            collections_seen = set()
            
            def format_elapsed_time(seconds: float) -> str:
                """Format elapsed time in human-readable form (no seconds display)."""
                if seconds < 60:
                    return f"{int(seconds)}s"
                elif seconds < 3600:
                    minutes = int(seconds // 60)
                    secs = int(seconds % 60)
                    return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
                else:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    if minutes > 0:
                        return f"{hours}h {minutes}m"
                    return f"{hours}h"
            
            # Register log callback - filter out DEBUG logs
            def log_callback(message: str, level: str = "info"):
                """Log callback to display migration service logs (excluding DEBUG)."""
                # Skip DEBUG logs
                if level.lower() == "debug":
                    return
                
                level_map = {
                    "info": ("[dim]", "dim"),
                    "warning": ("[yellow]", "yellow"),
                    "error": ("[bold red]", "bold red"),
                    "critical": ("[bold red]", "bold red")
                }
                style, close_tag = level_map.get(level.lower(), ("[dim]", "dim"))
                msg = message.rstrip('\n')
                
                # Only show errors prominently, keep info minimal
                if level.lower() in ("error", "critical"):
                    self.console.print(f"{style}❌ {msg}[/{close_tag}]")
                elif level.lower() == "warning":
                    self.console.print(f"{style}⚠️  {msg}[/{close_tag}]")
                # Info logs are too verbose, skip them
            
            add_log_callback(log_callback)
            
            # Progress callback - simplified
            def progress_callback(collection_id: str, current: int, total: Optional[int]):
                """Progress callback for migration - simplified display."""
                # Progress is shown in status callback, keep this minimal
                pass
            
            def status_callback(collection_id: str, status: str, missing: int = 0, 
                              migrated: int = 0, total: int = 0, current_batch: int = 0, 
                              state: str = "", total_batches: int = 0):
                """Status callback for migration - user-friendly display."""
                nonlocal processed_collections, total_collections, current_collection, collections_seen
                
                if collection_id not in collection_start_times:
                    collection_start_times[collection_id] = datetime.now(timezone.utc)
                    if collection_id not in collections_seen:
                        collections_seen.add(collection_id)
                        total_collections += 1
                    current_collection = collection_id
                
                coll_elapsed = (datetime.now(timezone.utc) - collection_start_times[collection_id]).total_seconds()
                total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                
                # Format elapsed times
                coll_elapsed_str = format_elapsed_time(coll_elapsed)
                total_elapsed_str = format_elapsed_time(total_elapsed)
                
                # Display based on status
                if status == "Starting":
                    processed_collections += 1
                    self.console.print()
                    self.console.print(f"[bold cyan]▶ Collection {processed_collections}/{total_collections}: {collection_id}[/bold cyan]")
                elif status == "Processing":
                    # Show progress: processed/total collections with elapsed time
                    # Use current collection index + 1 for display
                    current_idx = len(collections_seen)
                    progress_info = f"[{current_idx}/{total_collections}]"
                    
                    # Build status line
                    parts = [progress_info, collection_id]
                    if total > 0:
                        parts.append(f"{migrated:,}/{total:,} docs")
                    elif migrated > 0:
                        parts.append(f"{migrated:,} docs")
                    if total_batches > 0:
                        parts.append(f"Batch {current_batch}/{total_batches}")
                    parts.append(f"({coll_elapsed_str})")
                    
                    # Use carriage return to update same line
                    self.console.print(f"[cyan]{' | '.join(parts)}[/cyan]", end="\r")
                elif status == "Completed":
                    processed_collections += 1
                    self.console.print()  # Clear the progress line
                    self.console.print(f"[bold green]✓ [{processed_collections}/{total_collections}] {collection_id}: Completed ({coll_elapsed_str})[/bold green]")
                elif status == "Failed":
                    processed_collections += 1
                    self.console.print()  # Clear the progress line
                    self.console.print(f"[bold red]✗ [{processed_collections}/{total_collections}] {collection_id}: Failed after {coll_elapsed_str}[/bold red]")
                elif status == "Checking":
                    self.console.print(f"[yellow]🔍 Checking: {collection_id}...[/yellow]")
                elif status == "Synced":
                    self.console.print(f"[green]✓ {collection_id}: Already synced[/green]")
                elif status == "Skipped":
                    self.console.print(f"[dim]⊘ {collection_id}: Skipped[/dim]")
                elif status == "Pending":
                    self.console.print(f"[yellow]⏳ {collection_id}: {missing:,} missing documents[/yellow]")
                
                # Show overall progress at the end of each collection
                if status in ("Completed", "Failed"):
                    self.console.print(f"[dim]   Overall progress: {processed_collections}/{total_collections} collections | Total time: {total_elapsed_str}[/dim]")
            
            # Run migration based on mode
            self._run_migration(
                mode, migration_ops, source_config, target_config, 
                mysql_config, reverse, progress_callback, status_callback, start_time
            )
            
        except KeyboardInterrupt:
            def format_elapsed_time(seconds: float) -> str:
                if seconds < 60:
                    return f"{int(seconds)}s"
                elif seconds < 3600:
                    minutes = int(seconds // 60)
                    secs = int(seconds % 60)
                    return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
                else:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    if minutes > 0:
                        return f"{hours}h {minutes}m"
                    return f"{hours}h"
            
            total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            total_elapsed_str = format_elapsed_time(total_elapsed)
            self.console.print()
            self.ui.show_warning(f"Operation cancelled by user (after {total_elapsed_str})")
        except Exception as e:
            def format_elapsed_time(seconds: float) -> str:
                if seconds < 60:
                    return f"{int(seconds)}s"
                elif seconds < 3600:
                    minutes = int(seconds // 60)
                    secs = int(seconds % 60)
                    return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
                else:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    if minutes > 0:
                        return f"{hours}h {minutes}m"
                    return f"{hours}h"
            
            total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            total_elapsed_str = format_elapsed_time(total_elapsed)
            self.console.print()
            self.ui.show_error(f"Migration failed after {total_elapsed_str}: {e}")
            import traceback
            self.console.print()
            self.console.print("[bold red]Error Details:[/bold red]")
            self.console.print("[red]" + str(e) + "[/red]")
        
        self.ui.pause()
    
    def _run_migration(self, mode, migration_ops, source_config, target_config, 
                      mysql_config, reverse, progress_callback, status_callback, start_time):
        """Run migration based on mode."""
        if mode == "check":
            self.console.print("[bold cyan]🔍 Running in CHECK mode - checking synchronization[/bold cyan]")
            self.console.print()
            result = self._run_with_spinner(
                "Checking synchronization...",
                lambda: self._run_async(
                    migration_ops.check_sync(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        check_count=True
                    )
                )
            )
            self._display_check_results(result)
            
        elif mode == "migrate":
            self.console.print("[bold cyan]🔄 Running in MIGRATE mode - migrating all collections[/bold cyan]")
            self.console.print()
            result = self._run_with_spinner(
                "Migrating collections...",
                lambda: self._run_async(
                    migration_ops.migrate_all(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        reverse=reverse,
                        progress_callback=progress_callback,
                        status_callback=status_callback
                    )
                )
            )
            self._display_migration_results(result, start_time)
            
        elif mode == "migrate-usc":
            self.console.print("[bold cyan]🔍 Running in MIGRATE-USC mode - migrating only missing documents[/bold cyan]")
            self.console.print()
            result = self._run_with_spinner(
                "Migrating missing documents...",
                lambda: self._run_async(
                    migration_ops.migrate_with_checks(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        reverse=reverse,
                        progress_callback=progress_callback,
                        status_callback=status_callback
                    )
                )
            )
            self._display_migration_results(result, start_time)
    
    def _run_with_spinner(self, message: str, func):
        """Run a function with a spinner animation."""
        from rich.progress import Progress, SpinnerColumn, TextColumn
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            progress.add_task(description=message, total=None)
            return func()
    
    def _run_async(self, coro):
        """Run async function."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    
    def _display_check_results(self, result):
        """Display synchronization check results."""
        self.console.print()
        self.console.print(Panel("[bold]Synchronization Check Results[/bold]", style="cyan"))
        self.console.print()
        
        synced = result.get('synced_collections', [])
        missing = result.get('collections_to_migrate', [])
        
        if synced:
            self.console.print(f"[green]✓ Synced Collections: {len(synced)}[/green]")
            for coll in synced:
                self.console.print(f"  • {coll}")
        
        if missing:
            self.console.print(f"[yellow]⚠ Collections Needing Migration: {len(missing)}[/yellow]")
            for coll_info in missing:
                coll_id = coll_info.get('id', 'unknown')
                missing_count = coll_info.get('missing_points', 0)
                self.console.print(f"  • {coll_id}: {missing_count:,} missing points")
        
        if not synced and not missing:
            self.console.print("[dim]No collections found[/dim]")
    
    def _display_migration_results(self, result, start_time):
        """Display migration results."""
        def format_elapsed_time(seconds: float) -> str:
            """Format elapsed time in human-readable form."""
            if seconds < 60:
                return f"{int(seconds)}s"
            elif seconds < 3600:
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
            else:
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                if minutes > 0:
                    return f"{hours}h {minutes}m"
                return f"{hours}h"
        
        total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        total_elapsed_str = format_elapsed_time(total_elapsed)
        
        self.console.print()
        self.console.print(Panel("[bold]Migration Results[/bold]", style="green"))
        self.console.print()
        
        successful = result.get('successful_collections', [])
        failed = result.get('failed_collections', [])
        total_docs = result.get('total_documents', 0)
        
        self.console.print(f"[green]✓ Successful Collections:[/green] {len(successful)}")
        if successful:
            for coll_id in successful[:10]:  # Show first 10
                self.console.print(f"  • {coll_id}")
            if len(successful) > 10:
                self.console.print(f"  ... and {len(successful) - 10} more")
        
        if failed:
            self.console.print()
            self.console.print(f"[bold red]✗ Failed Collections:[/bold red] {len(failed)}")
            for coll_id in failed:
                self.console.print(f"  • [red]{coll_id}[/red]")
        
        self.console.print()
        self.console.print(f"[bold]Total Documents Migrated:[/bold] {total_docs:,}")
        self.console.print()
        self.console.print(Panel(f"[bold green]✅ Migration Completed![/bold green]\n[bold]Total Time: {total_elapsed_str}[/bold]", style="green"))
        self.console.print()
    

