"""
Qdrant Distributed Cluster Management

A modular package for managing Qdrant distributed cluster operations including
shard management, transfers, and cluster monitoring.

Architecture:
- models: Data models, enums, and DTOs
- client: Low-level API client for Qdrant operations
- services: Business logic and orchestration
- operations: High-level operation facades
- cli: Command-line interface utilities
"""

from qdrant_distributed.models import (
    ShardTransferMethod,
    ShardInfo,
    PeerInfo,
    ClusterInfo,
)
from qdrant_distributed.operations import (
    ShardOperations,
    ClusterOperations,
)
from qdrant_distributed.exceptions import (
    QdrantShardingError,
    ClusterConfigError,
    ShardTransferError,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "ShardTransferMethod",
    "ShardInfo",
    "PeerInfo",
    "ClusterInfo",
    # Operations
    "ShardOperations",
    "ClusterOperations",
    # Exceptions
    "QdrantShardingError",
    "ClusterConfigError",
    "ShardTransferError",
]

