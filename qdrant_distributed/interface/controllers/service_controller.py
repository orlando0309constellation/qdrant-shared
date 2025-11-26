"""
Service Controller - Manages service initialization and lifecycle.
"""

from typing import Optional
from qdrant_distributed import ShardOperations, ClusterOperations
from qdrant_distributed.client.qdrant_client import QdrantClientManager
from qdrant_distributed.config import MySQLManager, get_qdrant_url, get_qdrant_port, get_qdrant_api_key
from qdrant_distributed.config import get_mysql_host, get_mysql_port, get_mysql_user, get_mysql_password, get_mysql_database
from qdrant_distributed.services.mysql_service import MySQLService


class ServiceController:
    """Manages initialization and access to application services."""
    
    def __init__(self):
        self.shard_ops: Optional[ShardOperations] = None
        self.cluster_ops: Optional[ClusterOperations] = None
        self.mysql_service: Optional[MySQLService] = None
        self.is_initialized = False
    
    def initialize_qdrant(self):
        """Initialize Qdrant client and operations."""
        if not self.is_initialized:
            QdrantClientManager.initialize(
                url=get_qdrant_url(),
                port=get_qdrant_port(),
                api_key=get_qdrant_api_key()
            )
            self.shard_ops = ShardOperations()
            self.cluster_ops = ClusterOperations()
            self.is_initialized = True
    
    def ensure_mysql_initialized(self, force: bool = False):
        """Ensure MySQL is initialized if needed."""
        if self.mysql_service is None or force:
            MySQLManager.initialize(
                host=get_mysql_host(),
                port=get_mysql_port(),
                user=get_mysql_user(),
                password=get_mysql_password(),
                database=get_mysql_database()
            )
            self.mysql_service = MySQLService()
    
    def get_shard_ops(self) -> ShardOperations:
        """Get shard operations instance."""
        if not self.is_initialized:
            self.initialize_qdrant()
        return self.shard_ops
    
    def get_cluster_ops(self) -> ClusterOperations:
        """Get cluster operations instance."""
        if not self.is_initialized:
            self.initialize_qdrant()
        return self.cluster_ops
    
    def get_mysql_service(self) -> Optional[MySQLService]:
        """Get MySQL service instance."""
        return self.mysql_service

