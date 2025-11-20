"""
Configuration utilities for Qdrant client settings.
Centralizes environment variable reading to avoid duplication.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from pymongo import MongoClient
# Load environment variables once at module level
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE")
class MongoManager:
    @classmethod
    def initialize(cls, url: str = MONGO_URL):
        client= MongoClient(url)
        if client:
            cls.client = client
            cls.db = cls.client.get_database(MONGO_DATABASE)
        else:
            raise ValueError("Failed to connect to MongoDB")
    
    @classmethod
    def get_db(cls):
        if cls.db is None:
            raise ValueError("Database not initialized")
        return cls.db

    @classmethod
    def get_collection(cls, name: str):
        if cls.db is None:
            raise ValueError("Database not initialized")
        return cls.db.get_collection(name)

def get_qdrant_url(default: str = "localhost") -> str:
    """Get QDRANT_URL from environment with default."""
    return os.getenv("QDRANT_URL", default)


def get_qdrant_port(default: str = "6333") -> str:
    """Get QDRANT_PORT from environment with default."""
    return os.getenv("QDRANT_PORT", default)


def get_qdrant_api_key() -> Optional[str]:
    """Get QDRANT_API_KEY from environment."""
    return os.getenv("QDRANT_API_KEY")


def get_qdrant_https(default: Optional[bool] = None) -> Optional[bool]:
    """
    Get QDRANT_HTTPS from environment and convert to boolean.
    
    Args:
        default: Default value if env var is not set. If None, returns None.
        
    Returns:
        Boolean value or None if not set and no default provided.
    """
    https_str = os.getenv("QDRANT_HTTPS")
    if https_str is None:
        return default
    return https_str.lower() == "true"


def get_qdrant_config(
    url: Optional[str] = None,
    port: Optional[str] = None,
    api_key: Optional[str] = None,
    https: Optional[bool] = None
) -> tuple[str, str, Optional[str], bool]:
    """
    Get Qdrant configuration with fallback to environment variables.
    
    Args:
        url: Optional URL override
        port: Optional port override
        api_key: Optional API key override
        https: Optional HTTPS flag override
        
    Returns:
        Tuple of (url, port, api_key, https)
        Note: https will be a boolean (defaults to True if not set)
    """
    # For https, default to True if not provided (matching http_client behavior)
    if https is None:
        https = get_qdrant_https(default=True)
    # Ensure https is a boolean (not None)
    https_bool = https if https is not None else True
    
    return (
        url or get_qdrant_url(),
        port or get_qdrant_port(),
        api_key or get_qdrant_api_key(),
        https_bool
    )

