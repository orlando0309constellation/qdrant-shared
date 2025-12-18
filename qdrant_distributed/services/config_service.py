"""
SQLite configuration service for storing application settings.
"""

import sqlite3
import json
from typing import Optional, List, Dict
from pathlib import Path


class ConfigService:
    """SQLite-based configuration service for storing application settings."""
    
    _connection: Optional[sqlite3.Connection] = None
    _db_path: Optional[str] = None
    
    @classmethod
    def initialize(cls, db_path: Optional[str] = None):
        """
        Initialize SQLite database connection.
        
        Args:
            db_path: Optional path to SQLite database file. 
                    If None, uses default location in user's home directory.
        """
        if cls._connection is not None:
            return
        
        if db_path is None:
            # Use default location: ~/.qdrant-manager/config.db
            home_dir = Path.home()
            config_dir = home_dir / ".qdrant-manager"
            config_dir.mkdir(exist_ok=True)
            db_path = str(config_dir / "config.db")
        
        cls._db_path = db_path
        
        # Create connection
        cls._connection = sqlite3.connect(db_path, check_same_thread=False)
        cls._connection.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create table if it doesn't exist
        cls._create_table()
    
    @classmethod
    def _create_table(cls):
        """Create qdrantconfiguration table if it doesn't exist."""
        if cls._connection is None:
            raise ValueError("Database not initialized. Call initialize() first.")
        
        cursor = cls._connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qdrantconfiguration (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cls._connection.commit()
        cursor.close()
    
    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
        
        Returns:
            Configuration value or default
        """
        if cls._connection is None:
            cls.initialize()
        
        cursor = cls._connection.cursor()
        cursor.execute("SELECT value FROM qdrantconfiguration WHERE key = ?", (key,))
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return row['value']
        return default
    
    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """
        Get a configuration value as integer.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist or conversion fails
        
        Returns:
            Configuration value as integer or default
        """
        value = cls.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def set(cls, key: str, value: str):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value (will be converted to string)
        """
        if cls._connection is None:
            cls.initialize()
        
        cursor = cls._connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO qdrantconfiguration (key, value)
            VALUES (?, ?)
        """, (key, str(value)))
        cls._connection.commit()
        cursor.close()
    
    @classmethod
    def set_int(cls, key: str, value: int):
        """
        Set a configuration value as integer.
        
        Args:
            key: Configuration key
            value: Integer value to store
        """
        cls.set(key, str(value))
    
    @classmethod
    def delete(cls, key: str):
        """
        Delete a configuration key.
        
        Args:
            key: Configuration key to delete
        """
        if cls._connection is None:
            cls.initialize()
        
        cursor = cls._connection.cursor()
        cursor.execute("DELETE FROM qdrantconfiguration WHERE key = ?", (key,))
        cls._connection.commit()
        cursor.close()
    
    @classmethod
    def get_all(cls) -> dict:
        """
        Get all configuration values as a dictionary.
        
        Returns:
            Dictionary of all key-value pairs
        """
        if cls._connection is None:
            cls.initialize()
        
        cursor = cls._connection.cursor()
        cursor.execute("SELECT key, value FROM qdrantconfiguration")
        rows = cursor.fetchall()
        cursor.close()
        
        return {row['key']: row['value'] for row in rows}
    
    @classmethod
    def get_db_path(cls) -> str:
        """
        Get the path to the SQLite database file.
        
        Returns:
            Path to the database file
        """
        if cls._db_path is None:
            # Initialize to get the default path
            cls.initialize()
        return cls._db_path or str(Path.home() / ".qdrant-manager" / "config.db")
    
    @classmethod
    def close(cls):
        """Close the database connection."""
        if cls._connection is not None:
            cls._connection.close()
            cls._connection = None
    
    @classmethod
    def get_snapshot_urls(cls) -> List[Dict[str, any]]:
        """
        Get snapshot URLs configuration as a list of dictionaries.
        
        Returns:
            List of dictionaries with keys: url, port, https
            Each dict has: {"url": str, "port": str, "https": bool}
        """
        json_str = cls.get("SNAPSHOT_URLS")
        if json_str is None:
            return []
        try:
            urls = json.loads(json_str)
            # Ensure https is boolean
            for url_config in urls:
                if isinstance(url_config.get("https"), str):
                    url_config["https"] = url_config["https"].lower() == "true"
            return urls
        except (json.JSONDecodeError, TypeError):
            return []
    
    @classmethod
    def set_snapshot_urls(cls, urls: List[Dict[str, any]]):
        """
        Set snapshot URLs configuration.
        
        Args:
            urls: List of dictionaries with keys: url, port, https
                  Each dict should have: {"url": str, "port": str, "https": bool}
        """
        # Validate and normalize the data
        normalized_urls = []
        for url_config in urls:
            normalized = {
                "url": str(url_config.get("url", "")),
                "port": str(url_config.get("port", "")),
                "https": bool(url_config.get("https", False))
            }
            normalized_urls.append(normalized)
        
        json_str = json.dumps(normalized_urls)
        cls.set("SNAPSHOT_URLS", json_str)

