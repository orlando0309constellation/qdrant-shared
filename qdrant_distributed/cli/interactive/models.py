"""
Data models for Interactive CLI.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


@dataclass
class MigrationConfig:
    """Migration configuration."""
    name: str
    source_url: str
    source_port: int
    source_api_key: Optional[str]
    source_https: bool
    target_url: str
    target_port: int
    target_api_key: Optional[str]
    target_https: bool
    mysql_host: Optional[str] = None
    mysql_port: Optional[int] = None
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    mysql_database: Optional[str] = None
    use_default_mysql: bool = True
    reverse: bool = False
    enable_ai: bool = True  # Enable AI-generated summaries by default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'source_url': self.source_url,
            'source_port': self.source_port,
            'source_api_key': self.source_api_key,
            'source_https': self.source_https,
            'target_url': self.target_url,
            'target_port': self.target_port,
            'target_api_key': self.target_api_key,
            'target_https': self.target_https,
            'mysql_host': self.mysql_host,
            'mysql_port': self.mysql_port,
            'mysql_user': self.mysql_user,
            'mysql_password': self.mysql_password,
            'mysql_database': self.mysql_database,
            'use_default_mysql': self.use_default_mysql,
            'reverse': self.reverse,
            'enable_ai': self.enable_ai
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MigrationConfig':
        """Create from dictionary."""
        return cls(
            name=data.get('name', 'Unnamed'),
            source_url=data['source_url'],
            source_port=data['source_port'],
            source_api_key=data.get('source_api_key'),
            source_https=data.get('source_https', False),
            target_url=data['target_url'],
            target_port=data['target_port'],
            target_api_key=data.get('target_api_key'),
            target_https=data.get('target_https', False),
            mysql_host=data.get('mysql_host'),
            mysql_port=data.get('mysql_port'),
            mysql_user=data.get('mysql_user'),
            mysql_password=data.get('mysql_password'),
            mysql_database=data.get('mysql_database'),
            use_default_mysql=data.get('use_default_mysql', True),
            reverse=data.get('reverse', False),
            enable_ai=data.get('enable_ai', True)
        )
    
    def get_source_config(self) -> Dict[str, Any]:
        """Get source Qdrant config dict."""
        return {
            'url': self.source_url,
            'port': self.source_port,
            'api_key': self.source_api_key,
            'https': self.source_https
        }
    
    def get_target_config(self) -> Dict[str, Any]:
        """Get target Qdrant config dict."""
        return {
            'url': self.target_url,
            'port': self.target_port,
            'api_key': self.target_api_key,
            'https': self.target_https
        }
    
    def get_mysql_config(self) -> Optional[Dict[str, Any]]:
        """Get MySQL config dict."""
        if self.use_default_mysql:
            return None
        return {
            'host': self.mysql_host,
            'port': self.mysql_port,
            'user': self.mysql_user,
            'password': self.mysql_password,
            'database': self.mysql_database
        }
    
    def display_summary(self) -> str:
        """Get display summary."""
        source_key = f"{self.source_api_key[:6]}..." if self.source_api_key else "None"
        target_key = f"{self.target_api_key[:6]}..." if self.target_api_key else "None"
        mysql_info = "Default" if self.use_default_mysql else f"{self.mysql_host}:{self.mysql_port}"
        return (
            f"Name: {self.name}\n"
            f"Source: {self.source_url}:{self.source_port} (API: {source_key}, HTTPS: {self.source_https})\n"
            f"Target: {self.target_url}:{self.target_port} (API: {target_key}, HTTPS: {self.target_https})\n"
            f"MySQL: {mysql_info}\n"
            f"Reverse: {self.reverse}\n"
            f"AI Summaries: {'Enabled' if self.enable_ai else 'Disabled'}"
        )


@dataclass
class ConnectionConfig:
    """Qdrant connection configuration."""
    url: str = "localhost"
    port: str = "6333"
    https: bool = False
    api_key: Optional[str] = None
    name: Optional[str] = None  # Optional friendly name
    
    @property
    def display_url(self) -> str:
        scheme = "https" if self.https else "http"
        return f"{scheme}://{self.url}:{self.port}"
    
    @property
    def display_name(self) -> str:
        if self.name:
            return f"{self.name} ({self.display_url})"
        return self.display_url
    
    @classmethod
    def from_env(cls) -> 'ConnectionConfig':
        """Load configuration from environment variables."""
        return cls(
            url=os.getenv("QDRANT_URL", "localhost"),
            port=os.getenv("QDRANT_PORT", "6333"),
            https=os.getenv("QDRANT_HTTPS", "false").lower() == "true",
            api_key=os.getenv("QDRANT_API_KEY"),
            name="Default (from env)"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "port": self.port,
            "https": self.https,
            "api_key": self.api_key,
            "name": self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionConfig':
        """Create from dictionary."""
        return cls(
            url=data.get("url", "localhost"),
            port=data.get("port", "6333"),
            https=data.get("https", False),
            api_key=data.get("api_key"),
            name=data.get("name")
        )


class MenuAction(Enum):
    """Menu action types."""
    BACK = "back"
    EXIT = "exit"
    CONTINUE = "continue"

