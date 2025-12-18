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
            
            # Track elapsed time
            start_time = datetime.now(timezone.utc)
            collection_start_times = {}
            
            # Register log callback
            def log_callback(message: str, level: str = "info"):
                """Log callback to display migration service logs."""
                level_map = {
                    "debug": ("[dim]", "dim"),
                    "info": ("[cyan]", "cyan"),
                    "warning": ("[yellow]", "yellow"),
                    "error": ("[red]", "red"),
                    "critical": ("[bold red]", "bold red")
                }
                style, close_tag = level_map.get(level.lower(), ("[cyan]", "cyan"))
                msg = message.rstrip('\n')
                self.console.print(f"{style}{msg}[/{close_tag}]")
            
            add_log_callback(log_callback)
            
            # Progress and status callbacks
            def progress_callback(collection_id: str, current: int, total: Optional[int]):
                """Progress callback for migration."""
                if total is not None and current is not None and total > 0:
                    pct = int((current / total) * 100)
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    self.console.print(f"[cyan]  {collection_id}: {pct}% ({current}/{total}) - Elapsed: {elapsed:.1f}s[/cyan]")
                elif current is not None:
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    self.console.print(f"[cyan]  {collection_id}: {current} documents - Elapsed: {elapsed:.1f}s[/cyan]")
            
            def status_callback(collection_id: str, status: str, missing: int = 0, 
                              migrated: int = 0, total: int = 0, current_batch: int = 0, 
                              state: str = "", total_batches: int = 0):
                """Status callback for migration."""
                if collection_id not in collection_start_times:
                    collection_start_times[collection_id] = datetime.now(timezone.utc)
                
                coll_elapsed = (datetime.now(timezone.utc) - collection_start_times[collection_id]).total_seconds()
                total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                
                status_parts = []
                if state:
                    status_parts.append(state)
                if current_batch > 0:
                    batch_info = f"Batch {current_batch}"
                    if total_batches > 0:
                        batch_info += f"/{total_batches}"
                    status_parts.append(batch_info)
                if migrated > 0:
                    status_parts.append(f"{migrated:,} migrated")
                if missing > 0:
                    status_parts.append(f"{missing:,} missing")
                if total > 0:
                    status_parts.append(f"{total:,} total")
                
                status_msg = " | ".join(status_parts) if status_parts else status
                if coll_elapsed > 0:
                    status_msg += f" | {coll_elapsed:.1f}s"
                
                if status == "Starting":
                    self.console.print(f"[bold cyan]▶ Starting collection: {collection_id}[/bold cyan]")
                elif status == "Processing":
                    self.console.print(f"[cyan]  {collection_id}: {status_msg}[/cyan]")
                elif status == "Completed":
                    self.console.print(f"[bold green]✓ {collection_id}: Completed in {coll_elapsed:.1f}s (Total: {total_elapsed:.1f}s)[/bold green]")
                elif status == "Failed":
                    self.console.print(f"[bold red]✗ {collection_id}: Failed after {coll_elapsed:.1f}s[/bold red]")
                elif status == "Checking":
                    self.console.print(f"[yellow]🔍 {collection_id}: Checking synchronization...[/yellow]")
                elif status == "Synced":
                    self.console.print(f"[green]✓ {collection_id}: Already synced[/green]")
                elif status == "Skipped":
                    self.console.print(f"[dim]⊘ {collection_id}: Skipped[/dim]")
                elif status == "Pending":
                    self.console.print(f"[yellow]⏳ {collection_id}: Pending migration ({missing:,} missing)[/yellow]")
                else:
                    if status_msg:
                        self.console.print(f"[cyan]  {collection_id}: {status_msg}[/cyan]")
            
            # Run migration based on mode
            self._run_migration(
                mode, migration_ops, source_config, target_config, 
                mysql_config, reverse, progress_callback, status_callback, start_time
            )
            
        except KeyboardInterrupt:
            total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.console.print()
            self.ui.show_warning(f"Operation cancelled by user (after {total_elapsed:.1f}s)")
        except Exception as e:
            total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.ui.show_error(f"Migration failed after {total_elapsed:.1f}s: {e}")
            import traceback
            self.console.print()
            self.console.print("[dim]" + traceback.format_exc() + "[/dim]")
        
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
        total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        self.console.print()
        self.console.print(Panel("[bold]Migration Results[/bold]", style="green"))
        self.console.print()
        self.console.print(f"Total Documents: {result.get('total_documents', 0):,}")
        self.console.print(f"Successful Collections: {len(result.get('successful_collections', []))}")
        if result.get('failed_collections'):
            self.console.print(f"[red]Failed Collections: {len(result['failed_collections'])}[/red]")
            for coll_id in result['failed_collections']:
                self.console.print(f"  • {coll_id}")
        
        self.console.print()
        self.console.print(Panel(f"[bold green]✅ Migration Completed![/bold green]\n[bold]Total Elapsed Time: {total_elapsed:.2f}s[/bold]", style="green"))
        self.console.print()
    

