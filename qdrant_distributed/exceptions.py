"""
Custom exceptions for Qdrant distributed operations.
"""


class QdrantShardingError(Exception):
    """Base exception for Qdrant sharding operations."""
    pass


class ClusterConfigError(QdrantShardingError):
    """Exception raised for cluster configuration errors."""
    pass


class ShardTransferError(QdrantShardingError):
    """Exception raised for shard transfer operation errors."""
    pass


class PeerConnectionError(QdrantShardingError):
    """Exception raised for peer connection errors."""
    pass


class ValidationError(QdrantShardingError):
    """Exception raised for validation errors."""
    pass

