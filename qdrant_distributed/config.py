"""
Configuration utilities for Qdrant client settings.
Centralizes environment variable reading to avoid duplication.
Supports both SQLite configuration (GUI) and environment variables (CLI).
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables once at module level
load_dotenv()

# Lazy import to avoid circular dependencies
_config_service = None

def _get_config_service():
    """Get ConfigService instance (lazy import)."""
    global _config_service
    if _config_service is None:
        from qdrant_distributed.services.config_service import ConfigService
        _config_service = ConfigService
        # Initialize if not already initialized
        if _config_service._connection is None:
            _config_service.initialize()
    return _config_service

# MongoDB Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE")

# MySQL Configuration - with ConfigService fallback
def get_mysql_host(default: str = "localhost") -> str:
    """Get MYSQL_HOST from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("MYSQL_HOST") or os.getenv("MYSQL_HOST", default)

def get_mysql_port(default: int = 3306) -> int:
    """Get MYSQL_PORT from ConfigService or environment with default."""
    config_service = _get_config_service()
    port_str = config_service.get("MYSQL_PORT")
    if port_str:
        try:
            return int(port_str)
        except ValueError:
            pass
    return int(os.getenv("MYSQL_PORT", str(default)))

def get_mysql_user(default: str = "root") -> str:
    """Get MYSQL_USER from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("MYSQL_USER") or os.getenv("MYSQL_USER", default)

def get_mysql_password(default: str = "") -> str:
    """Get MYSQL_PASSWORD from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("MYSQL_PASSWORD") or os.getenv("MYSQL_PASSWORD", default)

def get_mysql_database(default: str = "qdrant_manager") -> str:
    """Get MYSQL_DATABASE from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("MYSQL_DATABASE") or os.getenv("MYSQL_DATABASE", default)

# Backward compatibility - module-level variables (evaluated at import time)
# Note: These are static values from environment at import time.
# For dynamic values, use the get_* functions instead.
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "qdrant_manager")

class MongoManager:
    """MongoDB connection manager with lazy import."""
    client = None
    db = None
    
    @classmethod
    def initialize(cls, url: str = MONGO_URL):
        """
        Initialize MongoDB connection.
        
        Args:
            url: MongoDB connection URL
        
        Raises:
            ImportError: If pymongo is not installed
        """
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError(
                "pymongo is not installed. Install it with: pip install pymongo>=4.15.4\n"
                "Or if using uv: uv pip install pymongo>=4.15.4"
            )
        
        cls.client = MongoClient(url)
        if cls.client:
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

class MySQLManager:
    """MySQL connection manager with lazy import."""
    connection = None
    db = None
    
    @classmethod
    def initialize(cls, host: str = None, port: int = None, user: str = None, 
                   password: str = None, database: str = None):
        """
        Initialize MySQL connection.
        
        Args:
            host: MySQL host (defaults to ConfigService or MYSQL_HOST env var)
            port: MySQL port (defaults to ConfigService or MYSQL_PORT env var)
            user: MySQL user (defaults to ConfigService or MYSQL_USER env var)
            password: MySQL password (defaults to ConfigService or MYSQL_PASSWORD env var)
            database: MySQL database name (defaults to ConfigService or MYSQL_DATABASE env var)
        
        Raises:
            ImportError: If mysql-connector-python is not installed
        """
        try:
            import mysql.connector
            from mysql.connector import Error
        except ImportError:
            raise ImportError(
                "mysql-connector-python is not installed. Install it with: pip install mysql-connector-python>=8.2.0\n"
                "Or if using uv: uv pip install mysql-connector-python>=8.2.0"
            )
        
        try:
            cls.connection = mysql.connector.connect(
                host=host or get_mysql_host(),
                port=port or get_mysql_port(),
                user=user or get_mysql_user(),
                password=password or get_mysql_password(),
                database=database or get_mysql_database(),
                autocommit=False
            )
            cls.db = cls.connection
            
            # Create tables if they don't exist
            cls._create_tables()
        except Error as e:
            raise ValueError(f"Failed to connect to MySQL: {e}")
    
    @classmethod
    def _create_tables(cls):
        """Create required tables if they don't exist and migrate peer_id to BIGINT if needed."""
        cursor = cls.connection.cursor()
        
        # Create peers table with snapshot tracking and JSON column for shards (optimized)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                snapshot_id BIGINT NOT NULL,
                peer_id BIGINT NOT NULL,
                uri VARCHAR(500),
                shards_json JSON COMMENT 'Array of shards as JSON for fast read/write',
                created_at DATETIME NOT NULL,
                INDEX idx_snapshot_id (snapshot_id),
                INDEX idx_peer_id (peer_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Add shards_json column if it doesn't exist (migration for existing tables)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'peers'
                AND COLUMN_NAME = 'shards_json'
            """)
            result = cursor.fetchone()
            has_shards_json = (result[0] if result else 0) > 0
            
            if not has_shards_json:
                cursor.execute("""
                    ALTER TABLE peers 
                    ADD COLUMN shards_json JSON COMMENT 'Array of shards as JSON for fast read/write'
                    AFTER uri
                """)
                cls.connection.commit()
        except Exception as e:
            # Column might already exist or there's a compatibility issue (e.g., old MySQL version)
            print(f"Note: Could not add shards_json column (may already exist or unsupported): {e}")
        
        # Create shards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shards (
                id INT AUTO_INCREMENT PRIMARY KEY,
                snapshot_id BIGINT NOT NULL,
                peer_id BIGINT NOT NULL,
                shard_id INT NOT NULL,
                points_count BIGINT NOT NULL,
                state VARCHAR(50) NOT NULL,
                created_at DATETIME NOT NULL,
                INDEX idx_snapshot_id (snapshot_id),
                INDEX idx_peer_id (peer_id),
                INDEX idx_shard_id (shard_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        cls.connection.commit()
        
        # Migrate existing tables: Change peer_id from INT to BIGINT if it exists as INT
        try:
            # Check if peers.peer_id is INT and needs migration
            cursor.execute("""
                SELECT DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'peers' 
                AND COLUMN_NAME = 'peer_id'
            """)
            result = cursor.fetchone()
            
            if result and result[0] in ('int', 'INT'):
                cursor.execute("ALTER TABLE peers MODIFY COLUMN peer_id BIGINT NOT NULL")
                print("[*] Migrated peers.peer_id from INT to BIGINT")
            
            # Check if shards.peer_id is INT and needs migration
            cursor.execute("""
                SELECT DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'shards' 
                AND COLUMN_NAME = 'peer_id'
            """)
            result = cursor.fetchone()
            
            if result and result[0] in ('int', 'INT'):
                cursor.execute("ALTER TABLE shards MODIFY COLUMN peer_id BIGINT NOT NULL")
                print("[*] Migrated shards.peer_id from INT to BIGINT")
            
            cls.connection.commit()
        except Exception as e:
            # Migration failed, but don't break initialization
            print(f"[!] Warning: Could not migrate peer_id columns: {e}")
            cls.connection.rollback()
        
        cursor.close()
    
    @classmethod
    def get_db(cls):
        if cls.db is None:
            raise ValueError("Database not initialized")
        return cls.db
    
    @classmethod
    def get_connection(cls):
        """Get MySQL connection."""
        if cls.connection is None:
            raise ValueError("Database not initialized")
        return cls.connection
    
    @classmethod
    def close(cls):
        """Close MySQL connection."""
        if cls.connection and cls.connection.is_connected():
            cls.connection.close()
            cls.connection = None
            cls.db = None

def get_qdrant_url(default: str = "localhost") -> str:
    """Get QDRANT_URL from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("QDRANT_URL") or os.getenv("QDRANT_URL", default)


def get_qdrant_port(default: str = "6333") -> str:
    """Get QDRANT_PORT from ConfigService or environment with default."""
    config_service = _get_config_service()
    return config_service.get("QDRANT_PORT") or os.getenv("QDRANT_PORT", default)


def get_qdrant_api_key() -> Optional[str]:
    """Get QDRANT_API_KEY from ConfigService or environment."""
    config_service = _get_config_service()
    return config_service.get("QDRANT_API_KEY") or os.getenv("QDRANT_API_KEY")


def get_qdrant_https(default: Optional[bool] = None) -> Optional[bool]:
    """
    Get QDRANT_HTTPS from ConfigService or environment and convert to boolean.
    
    Args:
        default: Default value if not set. If None, returns None.
        
    Returns:
        Boolean value or None if not set and no default provided.
    """
    config_service = _get_config_service()
    https_str = config_service.get("QDRANT_HTTPS") or os.getenv("QDRANT_HTTPS")
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

