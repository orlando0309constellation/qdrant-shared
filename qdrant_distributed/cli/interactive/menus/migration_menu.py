"""
Migration menu handler.
"""

from typing import Optional
from qdrant_distributed.cli.interactive.menus.base import BaseMenu
from qdrant_distributed.cli.interactive.models import MenuAction
from qdrant_distributed.cli.interactive.migration.config_manager import MigrationConfigManager
from qdrant_distributed.cli.interactive.migration.executor import MigrationExecutor


class MigrationMenu(BaseMenu):
    """Migration menu handler."""
    
    def __init__(self, *args, saved_migrations=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved_migrations = saved_migrations or []
    
    def display(self) -> MenuAction:
        """Display the migration menu."""
        while True:
            self.show_menu_header("Migration")
            
            options = [
                ("migrate_all", "🔄 Migrate All Collections"),
                ("migrate_missing", "🔍 Migrate Missing Only"),
                ("check_sync", "✓ Check Synchronization"),
            ]
            
            choice = self.ui.show_menu("Migration", options)
            
            if choice == "back":
                return MenuAction.CONTINUE
            elif choice == "migrate_all":
                self._execute("migrate")
            elif choice == "migrate_missing":
                self._execute("migrate-usc")
            elif choice == "check_sync":
                self._execute("check")
    
    def _execute(self, mode: str):
        """Execute migration operation."""
        self.ui.clear_screen()
        self.ui.show_banner(mini=True)
        
        # Create config manager and executor
        config_manager = MigrationConfigManager(
            self.console, self.prompts, self.current_config, self.saved_migrations
        )
        executor = MigrationExecutor(self.console, self.ui)
        
        # Select or create config
        mig_config = config_manager.select_or_create(mode)
        if not mig_config:
            self.ui.show_warning("Migration cancelled")
            self.ui.pause()
            return
        
        # Execute migration
        executor.execute(mode, mig_config, self.saved_migrations, self.config_manager)

