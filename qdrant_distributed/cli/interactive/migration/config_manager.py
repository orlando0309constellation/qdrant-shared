"""
Migration configuration management.
"""

from typing import Optional, List
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich import box

from qdrant_distributed.cli.interactive.models import MigrationConfig
from qdrant_distributed.cli.interactive.prompts import PromptHelper


class MigrationConfigManager:
    """Manages migration configurations."""
    
    def __init__(self, console, prompts: PromptHelper, current_config, saved_migrations: List[MigrationConfig]):
        self.console = console
        self.prompts = prompts
        self.current_config = current_config
        self.saved_migrations = saved_migrations
    
    def select_or_create(self, mode: str) -> Optional[MigrationConfig]:
        """Select existing migration config or create new one."""
        self.console.print()
        self.console.print(Panel("[bold]Migration Configuration[/bold]", style="cyan"))
        self.console.print()
        
        from qdrant_distributed.cli.interactive.ui import UIHelper
        ui = UIHelper(self.console)
        
        options = []
        if self.saved_migrations:
            for i, mig in enumerate(self.saved_migrations, 1):
                options.append((f"saved_{i}", f"📌 {mig.name}"))
        options.append(("new", "➕ Create New Configuration"))
        
        choice = ui.show_menu("Select Migration Configuration", options, show_back=True)
        
        if choice == "back":
            return None
        elif choice.startswith("saved_"):
            idx = int(choice.split("_")[1]) - 1
            selected = self.saved_migrations[idx]
            # Allow editing
            if Confirm.ask(f"Edit '{selected.name}' configuration?", default=False):
                return self.edit(selected, mode)
            return selected
        elif choice == "new":
            return self.create(mode)
        
        return None
    
    def create(self, mode: str) -> MigrationConfig:
        """Create a new migration configuration."""
        self.console.print()
        self.console.print(Panel("[bold]Create Migration Configuration[/bold]", style="cyan"))
        self.console.print()
        
        # Get name
        name = Prompt.ask("Configuration name", default=f"Migration {len(self.saved_migrations) + 1}")
        
        # Source config
        self.console.print()
        source_config = self.prompts.prompt_qdrant_config("Source Qdrant Configuration", self.current_config)
        
        # Target config
        self.console.print()
        target_config = self.prompts.prompt_qdrant_config("Target Qdrant Configuration")
        
        # MySQL config
        mysql_config, use_default = self.prompts.prompt_mysql_config()
        
        # Reverse
        reverse = False
        if mode in ["migrate", "migrate-usc"]:
            self.console.print()
            reverse = Confirm.ask("Reverse migration direction?", default=False)
        
        # AI summaries
        self.console.print()
        enable_ai = Confirm.ask("Enable AI-generated summaries?", default=True)
        
        # Create config
        return MigrationConfig(
            name=name,
            source_url=source_config['url'],
            source_port=source_config['port'],
            source_api_key=source_config['api_key'],
            source_https=source_config['https'],
            target_url=target_config['url'],
            target_port=target_config['port'],
            target_api_key=target_config['api_key'],
            target_https=target_config['https'],
            mysql_host=mysql_config.get('host') if mysql_config else None,
            mysql_port=mysql_config.get('port') if mysql_config else None,
            mysql_user=mysql_config.get('user') if mysql_config else None,
            mysql_password=mysql_config.get('password') if mysql_config else None,
            mysql_database=mysql_config.get('database') if mysql_config else None,
            use_default_mysql=use_default,
            reverse=reverse,
            enable_ai=enable_ai
        )
    
    def edit(self, config: MigrationConfig, mode: str) -> MigrationConfig:
        """Edit an existing migration configuration."""
        self.console.print()
        self.console.print(Panel(f"[bold]Edit: {config.name}[/bold]", style="cyan"))
        self.console.print()
        
        # Show current values and allow editing
        self.console.print("[bold]Current Configuration:[/bold]")
        self.display_summary(config)
        self.console.print()
        
        from qdrant_distributed.cli.interactive.ui import UIHelper
        ui = UIHelper(self.console)
        
        # Edit options
        options = [
            ("name", "📝 Edit Name"),
            ("source", "🔵 Edit Source Qdrant"),
            ("target", "🟢 Edit Target Qdrant"),
            ("mysql", "🗄️  Edit MySQL"),
            ("reverse", "🔄 Toggle Reverse"),
            ("ai", "🤖 Toggle AI Summaries"),
            ("done", "✅ Done Editing")
        ]
        
        edited_config = MigrationConfig(
            name=config.name,
            source_url=config.source_url,
            source_port=config.source_port,
            source_api_key=config.source_api_key,
            source_https=config.source_https,
            target_url=config.target_url,
            target_port=config.target_port,
            target_api_key=config.target_api_key,
            target_https=config.target_https,
            mysql_host=config.mysql_host,
            mysql_port=config.mysql_port,
            mysql_user=config.mysql_user,
            mysql_password=config.mysql_password,
            mysql_database=config.mysql_database,
            use_default_mysql=config.use_default_mysql,
            reverse=config.reverse,
            enable_ai=getattr(config, 'enable_ai', True)
        )
        
        while True:
            choice = ui.show_menu("Edit Configuration", options, show_back=False)
            
            if choice == "name":
                new_name = Prompt.ask("Configuration name", default=edited_config.name)
                edited_config.name = new_name
                ui.show_success(f"Name updated to: {new_name}")
            elif choice == "source":
                source_config = self.prompts.prompt_qdrant_config("Source Qdrant Configuration")
                edited_config.source_url = source_config['url']
                edited_config.source_port = source_config['port']
                edited_config.source_api_key = source_config['api_key']
                edited_config.source_https = source_config['https']
                ui.show_success("Source configuration updated")
            elif choice == "target":
                target_config = self.prompts.prompt_qdrant_config("Target Qdrant Configuration")
                edited_config.target_url = target_config['url']
                edited_config.target_port = target_config['port']
                edited_config.target_api_key = target_config['api_key']
                edited_config.target_https = target_config['https']
                ui.show_success("Target configuration updated")
            elif choice == "mysql":
                mysql_config, use_default = self.prompts.prompt_mysql_config()
                if mysql_config:
                    edited_config.mysql_host = mysql_config.get('host')
                    edited_config.mysql_port = mysql_config.get('port')
                    edited_config.mysql_user = mysql_config.get('user')
                    edited_config.mysql_password = mysql_config.get('password')
                    edited_config.mysql_database = mysql_config.get('database')
                edited_config.use_default_mysql = use_default
                ui.show_success("MySQL configuration updated")
            elif choice == "reverse":
                edited_config.reverse = not edited_config.reverse
                status = "enabled" if edited_config.reverse else "disabled"
                ui.show_success(f"Reverse migration {status}")
            elif choice == "ai":
                edited_config.enable_ai = not edited_config.enable_ai
                status = "enabled" if edited_config.enable_ai else "disabled"
                ui.show_success(f"AI summaries {status}")
            elif choice == "done":
                break
            
            self.console.print()
            self.display_summary(edited_config)
            self.console.print()
        
        return edited_config
    
    def display_summary(self, config: MigrationConfig):
        """Display migration configuration summary with API keys."""
        source_key = f"{config.source_api_key[:6]}..." if config.source_api_key else "[dim]None[/dim]"
        target_key = f"{config.target_api_key[:6]}..." if config.target_api_key else "[dim]None[/dim]"
        mysql_info = "[dim]Default[/dim]" if config.use_default_mysql else f"{config.mysql_host}:{config.mysql_port}"
        reverse_text = "[yellow]YES (Target → Source)[/yellow]" if config.reverse else "[green]NO (Source → Target)[/green]"
        
        table = Table(box=box.ROUNDED, title=f"Configuration: {config.name}")
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Source URL", f"{config.source_url}:{config.source_port}")
        table.add_row("Source HTTPS", "✓" if config.source_https else "✗")
        table.add_row("Source API Key", source_key)
        table.add_row("", "")  # Spacer
        table.add_row("Target URL", f"{config.target_url}:{config.target_port}")
        table.add_row("Target HTTPS", "✓" if config.target_https else "✗")
        table.add_row("Target API Key", target_key)
        table.add_row("", "")  # Spacer
        table.add_row("MySQL", mysql_info)
        table.add_row("Reverse Migration", reverse_text)
        ai_status = "[green]Enabled[/green]" if getattr(config, 'enable_ai', True) else "[yellow]Disabled[/yellow]"
        table.add_row("AI Summaries", ai_status)
        
        self.console.print(table)

