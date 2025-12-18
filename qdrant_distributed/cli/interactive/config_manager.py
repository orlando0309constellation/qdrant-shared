"""
Configuration management for Interactive CLI.
"""

import json
from typing import List, Optional
from qdrant_distributed.services.config_service import ConfigService
from qdrant_distributed.cli.interactive.models import ConnectionConfig, MigrationConfig


class ConfigManager:
    """Manages saved configurations."""
    
    CONFIG_SAVED_CONNECTIONS = "CLI_SAVED_CONNECTIONS"
    CONFIG_LAST_CONNECTION = "CLI_LAST_CONNECTION"
    CONFIG_RECENT_COLLECTIONS = "CLI_RECENT_COLLECTIONS"
    CONFIG_SAVED_MIGRATIONS = "CLI_SAVED_MIGRATIONS"
    
    def __init__(self):
        ConfigService.initialize()
    
    def load_saved_connections(self) -> List[ConnectionConfig]:
        """Load saved connections from storage."""
        try:
            data = ConfigService.get(self.CONFIG_SAVED_CONNECTIONS)
            if data:
                connections = json.loads(data)
                return [ConnectionConfig.from_dict(c) for c in connections]
        except (json.JSONDecodeError, Exception):
            pass
        return []
    
    def save_connections(self, connections: List[ConnectionConfig]):
        """Save connections to storage."""
        data = [c.to_dict() for c in connections]
        ConfigService.set(self.CONFIG_SAVED_CONNECTIONS, json.dumps(data))
    
    def add_saved_connection(self, connections: List[ConnectionConfig], config: ConnectionConfig):
        """Add or update a connection in the list."""
        # Check if already exists (by URL)
        for i, existing in enumerate(connections):
            if existing.url == config.url and existing.port == config.port:
                # Update existing
                connections[i] = config
                self.save_connections(connections)
                return
        # Add new
        connections.append(config)
        self.save_connections(connections)
    
    def load_last_connection(self) -> Optional[ConnectionConfig]:
        """Load last used connection from storage."""
        try:
            data = ConfigService.get(self.CONFIG_LAST_CONNECTION)
            if data:
                return ConnectionConfig.from_dict(json.loads(data))
        except (json.JSONDecodeError, Exception):
            pass
        return None
    
    def save_last_connection(self, config: ConnectionConfig):
        """Save current connection as last used."""
        ConfigService.set(self.CONFIG_LAST_CONNECTION, json.dumps(config.to_dict()))
    
    def load_recent_collections(self) -> List[str]:
        """Load recent collections from storage."""
        try:
            data = ConfigService.get(self.CONFIG_RECENT_COLLECTIONS)
            if data:
                return json.loads(data)
        except (json.JSONDecodeError, Exception):
            pass
        return []
    
    def save_recent_collections(self, collections: List[str]):
        """Save recent collections to storage."""
        # Keep only last 10 collections
        collections = collections[:10]
        ConfigService.set(self.CONFIG_RECENT_COLLECTIONS, json.dumps(collections))
    
    def add_recent_collection(self, collections: List[str], collection_name: str):
        """Add a collection to recent list."""
        if collection_name in collections:
            collections.remove(collection_name)
        collections.insert(0, collection_name)
        self.save_recent_collections(collections)
    
    def load_saved_migrations(self) -> List[MigrationConfig]:
        """Load saved migration configs from storage."""
        try:
            data = ConfigService.get(self.CONFIG_SAVED_MIGRATIONS)
            if data:
                migrations = json.loads(data)
                return [MigrationConfig.from_dict(m) for m in migrations]
        except (json.JSONDecodeError, Exception):
            pass
        return []
    
    def save_migrations(self, migrations: List[MigrationConfig]):
        """Save migration configs to storage."""
        data = [m.to_dict() for m in migrations]
        ConfigService.set(self.CONFIG_SAVED_MIGRATIONS, json.dumps(data))
    
    def add_saved_migration(self, migrations: List[MigrationConfig], config: MigrationConfig):
        """Add or update a migration config."""
        # Check if already exists (by name)
        for i, existing in enumerate(migrations):
            if existing.name == config.name:
                # Update existing
                migrations[i] = config
                self.save_migrations(migrations)
                return
        # Add new
        migrations.append(config)
        self.save_migrations(migrations)

