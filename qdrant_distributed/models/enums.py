"""
Enumerations for Qdrant distributed operations.
"""

from enum import Enum


class ShardTransferMethod(str, Enum):
    """Available methods for shard transfer operations."""
    
    STREAM_RECORDS = "stream_records"
    SNAPSHOT = "snapshot"
    WAL_DELTA = "wal_delta"
    RESHARDING_STREAM_RECORDS = "resharding_stream_records"
    
    @classmethod
    def get_default(cls) -> "ShardTransferMethod":
        """Get the default transfer method (best for most cases)."""
        return cls.STREAM_RECORDS
    
    @classmethod
    def list_methods(cls) -> list[str]:
        """Get list of all available methods."""
        return [method.value for method in cls]


class ShardState(str, Enum):
    """Possible states of a shard."""
    
    ACTIVE = "Active"
    DEAD = "Dead"
    PARTIAL = "Partial"
    INITIALIZING = "Initializing"
    LISTENER = "Listener"
    PARTIAL_SNAPSHOT = "PartialSnapshot"
    RECOVERY = "Recovery"
    RESHARDING = "Resharding"
    RESHARDING_SCALE_DOWN = "ReshardingScaleDown"
    ACTIVE_READ = "ActiveRead"


class OperationType(str, Enum):
    """Types of cluster operations."""
    
    MOVE_SHARD = "move_shard"
    REPLICATE_SHARD = "replicate_shard"
    ABORT_TRANSFER = "abort_transfer"
    DROP_REPLICA = "drop_replica"

