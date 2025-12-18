"""
Qdrant Snapshot Service - Handles snapshot operations for collections and clusters.

This module provides a comprehensive API for managing Qdrant snapshots at three levels:
1. Collection snapshots - Backup/restore individual collections
2. Full (cluster) snapshots - Backup/restore the entire Qdrant instance
3. Shard snapshots - Backup/restore individual shards (advanced)

Usage:
    # Static method (backwards compatible)
    snapshots = SnapshotService.list_collection_snapshots(url, port, https, api_key, collection_name)
    
    # Instance method (recommended for new code)
    service = SnapshotService(url, port, https, api_key)
    snapshots = service.list_collection_snapshots_impl(collection_name)
"""

import logging
import time
from enum import Enum
from functools import wraps
from typing import List, Dict, Optional, Any, Callable, TypeVar, Union

import requests
from qdrant_client import QdrantClient

from qdrant_distributed.services.config_service import ConfigService


# Setup module logger
logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar('T')


class SnapshotPriority(str, Enum):
    """Priority for snapshot recovery operations."""
    LOW = "low"
    NORMAL = "normal"
    SNAPSHOT = "snapshot"  # Prioritize snapshot loading over serving


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (requests.exceptions.RequestException, ConnectionError, TimeoutError)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator with exponential backoff for network operations.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator


class SnapshotService:
    """
    Service for managing Qdrant snapshots.
    
    Supports three types of snapshots:
    - Collection snapshots: Backup/restore individual collections
    - Full snapshots: Backup/restore the entire Qdrant instance  
    - Shard snapshots: Backup/restore individual shards (distributed mode)
    
    Can be used via static methods (backwards compatible) or as an instance.
    """
    
    # Default timeouts (in seconds)
    DEFAULT_TIMEOUT = 60
    SNAPSHOT_TIMEOUT = 3600  # 1 hour for snapshot operations
    DOWNLOAD_TIMEOUT = 3600
    
    # ========================================================================
    # Initialization and Client Management
    # ========================================================================
    
    def __init__(
        self,
        url: str,
        port: str,
        https: bool = False,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        snapshot_timeout: int = SNAPSHOT_TIMEOUT
    ):
        """
        Initialize SnapshotService.
        
        Args:
            url: Qdrant server hostname or IP
            port: Qdrant server port
            https: Use HTTPS connection
            api_key: API key for authentication
            timeout: Default timeout for operations
            snapshot_timeout: Timeout for long-running snapshot operations
        """
        self._url = url
        self._port = port
        self._https = https
        self._api_key = api_key
        self._timeout = timeout
        self._snapshot_timeout = snapshot_timeout
        
        logger.info(f"SnapshotService initialized for {'https' if https else 'http'}://{url}:{port}")
    
    def _get_client(self, timeout: Optional[int] = None) -> QdrantClient:
        """Create a QdrantClient with specified timeout."""
        scheme = "https" if self._https else "http"
        effective_timeout = timeout or self._timeout
        
        return QdrantClient(
            url=f"{scheme}://{self._url}:{self._port}",
            api_key=self._api_key,
            timeout=effective_timeout
        )
    
    def _get_base_url(self) -> str:
        """Get base URL for direct HTTP requests."""
        scheme = "https" if self._https else "http"
        return f"{scheme}://{self._url}:{self._port}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for direct requests."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["api-key"] = self._api_key
        return headers
    
    @staticmethod
    def _snapshot_to_dict(snapshot: Any) -> Dict[str, Any]:
        """Convert snapshot object to dictionary."""
        if isinstance(snapshot, dict):
            return snapshot
        
        result = {}
        for attr in ['name', 'size', 'creation_time', 'checksum']:
            if hasattr(snapshot, attr):
                result[attr] = getattr(snapshot, attr)
        
        if not result:
            try:
                return dict(snapshot)
            except (TypeError, ValueError):
                logger.warning(f"Could not convert snapshot to dict: {type(snapshot)}")
                return {"name": str(snapshot), "size": 0}
        
        return result
    
    # ========================================================================
    # Collection Snapshots - Instance Methods
    # ========================================================================
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def create_collection_snapshot_impl(
        self,
        collection_name: str,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Create a snapshot for a collection.
        
        Args:
            collection_name: Name of the collection to snapshot
            wait: Wait for operation to complete (default: True)
            
        Returns:
            Snapshot information dict with name, size, creation_time
        """
        logger.info(f"Creating snapshot for collection '{collection_name}' (wait={wait})")
        
        client = self._get_client(timeout=self._snapshot_timeout)
        result = client.create_snapshot(collection_name=collection_name, wait=wait)
        
        snapshot_dict = self._snapshot_to_dict(result)
        logger.info(f"Snapshot created: {snapshot_dict.get('name', 'unknown')}")
        return snapshot_dict
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def list_collection_snapshots_impl(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        List all snapshots for a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            List of snapshot dictionaries
        """
        logger.debug(f"Listing snapshots for collection '{collection_name}'")
        
        client = self._get_client()
        result = client.list_snapshots(collection_name=collection_name)
        
        snapshots = []
        for snapshot in (result if isinstance(result, list) else []):
            try:
                snapshots.append(self._snapshot_to_dict(snapshot))
            except Exception as e:
                logger.warning(f"Failed to convert snapshot: {e}")
        
        logger.debug(f"Found {len(snapshots)} snapshots")
        return snapshots
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def recover_collection_snapshot_impl(
        self,
        collection_name: str,
        location: str,
        priority: Optional[Union[SnapshotPriority, str]] = None,
        checksum: Optional[str] = None,
        wait: bool = True,
        location_api_key: Optional[str] = None
    ) -> bool:
        """
        Recover a collection from a snapshot.
        
        Args:
            collection_name: Name of the collection to recover
            location: Snapshot location - can be:
                - URL to download snapshot from (http://, https://, s3://)
                - Local file path on the Qdrant server
            priority: Recovery priority (low, normal, snapshot)
                - "low": Minimize impact on serving
                - "normal": Balance between speed and serving
                - "snapshot": Prioritize recovery speed
            checksum: Expected SHA-256 checksum for validation
            wait: Wait for recovery to complete (default: True)
            location_api_key: API key for accessing the snapshot location (if remote)
            
        Returns:
            True if recovery initiated/completed successfully
        """
        logger.info(
            f"Recovering collection '{collection_name}' from '{location}' "
            f"(priority={priority}, wait={wait})"
        )
        
        client = self._get_client(timeout=self._snapshot_timeout)
        
        # Convert string priority to enum if needed
        priority_value = None
        if priority:
            if isinstance(priority, str):
                priority_value = priority.lower()
            else:
                priority_value = priority.value
        
        try:
            client.recover_snapshot(
                collection_name=collection_name,
                location=location,
                priority=priority_value,
                checksum=checksum,
                wait=wait,
                api_key=location_api_key
            )
            logger.info(f"Collection '{collection_name}' recovery {'completed' if wait else 'initiated'}")
            return True
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            raise
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def delete_collection_snapshot_impl(
        self,
        collection_name: str,
        snapshot_name: str,
        wait: bool = True
    ) -> bool:
        """
        Delete a collection snapshot.
        
        Args:
            collection_name: Name of the collection
            snapshot_name: Name of the snapshot to delete
            wait: Wait for deletion to complete
            
        Returns:
            True if successful
        """
        logger.info(f"Deleting snapshot '{snapshot_name}' from collection '{collection_name}'")
        
        client = self._get_client()
        client.delete_snapshot(
            collection_name=collection_name,
            snapshot_name=snapshot_name,
            wait=wait
        )
        
        logger.info(f"Snapshot '{snapshot_name}' deleted")
        return True
    
    # ========================================================================
    # Full (Cluster) Snapshots - Instance Methods
    # ========================================================================
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def create_full_snapshot_impl(self, wait: bool = True) -> Dict[str, Any]:
        """
        Create a full snapshot of the entire Qdrant instance.
        
        This creates a snapshot of all collections and data.
        
        Args:
            wait: Wait for operation to complete
            
        Returns:
            Snapshot information dict
        """
        logger.info(f"Creating full snapshot (wait={wait})")
        
        client = self._get_client(timeout=self._snapshot_timeout)
        result = client.create_full_snapshot(wait=wait)
        
        snapshot_dict = self._snapshot_to_dict(result)
        logger.info(f"Full snapshot created: {snapshot_dict.get('name', 'unknown')}")
        return snapshot_dict
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def list_full_snapshots_impl(self) -> List[Dict[str, Any]]:
        """
        List all full (cluster) snapshots.
        
        Returns:
            List of snapshot dictionaries
        """
        logger.debug("Listing full snapshots")
        
        client = self._get_client()
        result = client.list_full_snapshots()
        
        snapshots = []
        for snapshot in (result if isinstance(result, list) else []):
            try:
                snapshot_dict = self._snapshot_to_dict(snapshot)
                snapshot_dict["type"] = "full"
                snapshots.append(snapshot_dict)
            except Exception as e:
                logger.warning(f"Failed to convert snapshot: {e}")
        
        logger.debug(f"Found {len(snapshots)} full snapshots")
        return snapshots
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def delete_full_snapshot_impl(self, snapshot_name: str, wait: bool = True) -> bool:
        """
        Delete a full snapshot.
        
        Args:
            snapshot_name: Name of the snapshot to delete
            wait: Wait for deletion to complete
            
        Returns:
            True if successful
        """
        logger.info(f"Deleting full snapshot '{snapshot_name}'")
        
        client = self._get_client()
        client.delete_full_snapshot(snapshot_name=snapshot_name, wait=wait)
        
        logger.info(f"Full snapshot '{snapshot_name}' deleted")
        return True
    
    # ========================================================================
    # Shard Snapshots - Instance Methods (for distributed deployments)
    # ========================================================================
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def create_shard_snapshot_impl(
        self,
        collection_name: str,
        shard_id: int,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Create a snapshot for a specific shard.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard
            wait: Wait for operation to complete
            
        Returns:
            Snapshot information dict
        """
        logger.info(f"Creating shard snapshot for '{collection_name}' shard {shard_id}")
        
        client = self._get_client(timeout=self._snapshot_timeout)
        result = client.create_shard_snapshot(
            collection_name=collection_name,
            shard_id=shard_id,
            wait=wait
        )
        
        snapshot_dict = self._snapshot_to_dict(result)
        logger.info(f"Shard snapshot created: {snapshot_dict.get('name', 'unknown')}")
        return snapshot_dict
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def list_shard_snapshots_impl(
        self,
        collection_name: str,
        shard_id: int
    ) -> List[Dict[str, Any]]:
        """
        List snapshots for a specific shard.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard
            
        Returns:
            List of snapshot dictionaries
        """
        logger.debug(f"Listing shard snapshots for '{collection_name}' shard {shard_id}")
        
        client = self._get_client()
        result = client.list_shard_snapshots(
            collection_name=collection_name,
            shard_id=shard_id
        )
        
        snapshots = []
        for snapshot in (result if isinstance(result, list) else []):
            try:
                snapshot_dict = self._snapshot_to_dict(snapshot)
                snapshot_dict["shard_id"] = shard_id
                snapshots.append(snapshot_dict)
            except Exception as e:
                logger.warning(f"Failed to convert snapshot: {e}")
        
        return snapshots
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def recover_shard_snapshot_impl(
        self,
        collection_name: str,
        shard_id: int,
        location: str,
        priority: Optional[Union[SnapshotPriority, str]] = None,
        checksum: Optional[str] = None,
        wait: bool = True,
        location_api_key: Optional[str] = None
    ) -> bool:
        """
        Recover a shard from a snapshot.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard to recover
            location: Snapshot location (URL or local path)
            priority: Recovery priority
            checksum: Expected checksum for validation
            wait: Wait for recovery to complete
            location_api_key: API key for remote snapshot location
            
        Returns:
            True if successful
        """
        logger.info(f"Recovering shard {shard_id} of '{collection_name}' from '{location}'")
        
        client = self._get_client(timeout=self._snapshot_timeout)
        
        priority_value = None
        if priority:
            priority_value = priority.value if isinstance(priority, SnapshotPriority) else priority.lower()
        
        client.recover_shard_snapshot(
            collection_name=collection_name,
            shard_id=shard_id,
            location=location,
            priority=priority_value,
            checksum=checksum,
            wait=wait,
            api_key=location_api_key
        )
        
        logger.info(f"Shard {shard_id} recovery {'completed' if wait else 'initiated'}")
        return True
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def delete_shard_snapshot_impl(
        self,
        collection_name: str,
        shard_id: int,
        snapshot_name: str,
        wait: bool = True
    ) -> bool:
        """
        Delete a shard snapshot.
        
        Args:
            collection_name: Name of the collection
            shard_id: ID of the shard
            snapshot_name: Name of the snapshot
            wait: Wait for deletion to complete
            
        Returns:
            True if successful
        """
        logger.info(f"Deleting shard snapshot '{snapshot_name}' from shard {shard_id}")
        
        client = self._get_client()
        client.delete_shard_snapshot(
            collection_name=collection_name,
            shard_id=shard_id,
            snapshot_name=snapshot_name,
            wait=wait
        )
        
        logger.info(f"Shard snapshot '{snapshot_name}' deleted")
        return True
    
    # ========================================================================
    # Utility Methods - Instance Methods
    # ========================================================================
    
    def get_snapshot_download_url(
        self,
        collection_name: str,
        snapshot_name: str
    ) -> str:
        """
        Get the download URL for a collection snapshot.
        
        Args:
            collection_name: Name of the collection
            snapshot_name: Name of the snapshot
            
        Returns:
            Full URL to download the snapshot
        """
        return f"{self._get_base_url()}/collections/{collection_name}/snapshots/{snapshot_name}"
    
    def get_full_snapshot_download_url(self, snapshot_name: str) -> str:
        """
        Get the download URL for a full snapshot.
        
        Args:
            snapshot_name: Name of the snapshot
            
        Returns:
            Full URL to download the snapshot
        """
        return f"{self._get_base_url()}/snapshots/{snapshot_name}"
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def download_snapshot_impl(
        self,
        collection_name: str,
        snapshot_name: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Download a collection snapshot to local file.
        
        Args:
            collection_name: Name of the collection
            snapshot_name: Name of the snapshot
            output_path: Local path to save file (default: snapshot_name)
            
        Returns:
            Path to downloaded file
        """
        url = self.get_snapshot_download_url(collection_name, snapshot_name)
        output = output_path or snapshot_name
        
        logger.info(f"Downloading snapshot from {url}")
        
        response = requests.get(
            url,
            headers=self._get_headers(),
            stream=True,
            timeout=self.DOWNLOAD_TIMEOUT
        )
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
        
        logger.info(f"Downloaded {downloaded} bytes to {output}")
        return output
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_collections_impl(self) -> List[str]:
        """
        Get list of all collection names.
        
        Returns:
            List of collection names
        """
        logger.debug("Fetching collections list")
        
        client = self._get_client()
        collections = client.get_collections().collections
        
        names = [c.name for c in collections]
        logger.debug(f"Found {len(names)} collections")
        return names
    
    # ========================================================================
    # Static Methods (Backwards Compatible API)
    # ========================================================================
    
    @staticmethod
    def _create_service(url: str, port: str, https: bool, api_key: Optional[str]) -> 'SnapshotService':
        """Create service instance from static method parameters."""
        return SnapshotService(url=url, port=port, https=https, api_key=api_key)
    
    # --- Collection Snapshots (Static) ---
    
    @staticmethod
    def create_collection_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str,
        wait: bool = True
    ) -> Dict[str, Any]:
        """Create a collection snapshot (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.create_collection_snapshot_impl(collection_name, wait=wait)
    
    @staticmethod
    def list_collection_snapshots(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str
    ) -> List[Dict[str, Any]]:
        """List collection snapshots (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.list_collection_snapshots_impl(collection_name)
    
    @staticmethod
    def recover_collection_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str,
        snapshot_location: str,
        priority: Optional[str] = None,
        checksum: Optional[str] = None,
        wait: bool = True,
        location_api_key: Optional[str] = None
    ) -> bool:
        """
        Recover a collection from snapshot (static method).
        
        Args:
            url: Qdrant server URL
            port: Qdrant server port
            https: Use HTTPS
            api_key: Qdrant API key
            collection_name: Collection to recover
            snapshot_location: URL or path to snapshot
            priority: Recovery priority ("low", "normal", "snapshot")
            checksum: Expected SHA-256 checksum
            wait: Wait for completion
            location_api_key: API key for snapshot location
        """
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.recover_collection_snapshot_impl(
            collection_name=collection_name,
            location=snapshot_location,
            priority=priority,
            checksum=checksum,
            wait=wait,
            location_api_key=location_api_key
        )
    
    @staticmethod
    def delete_collection_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str,
        snapshot_name: str,
        wait: bool = True
    ) -> bool:
        """Delete a collection snapshot (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.delete_collection_snapshot_impl(collection_name, snapshot_name, wait=wait)
    
    # --- Full (Cluster) Snapshots (Static) ---
    
    @staticmethod
    def create_cluster_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        wait: bool = True
    ) -> Dict[str, Any]:
        """Create a full cluster snapshot (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.create_full_snapshot_impl(wait=wait)
    
    @staticmethod
    def list_cluster_snapshots(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str]
    ) -> List[Dict[str, Any]]:
        """List all full cluster snapshots (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.list_full_snapshots_impl()
    
    @staticmethod
    def recover_cluster_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        snapshot_location: str,
        priority: Optional[str] = None,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Recover cluster from a full snapshot.
        
        Note: Full snapshot recovery requires server restart with specific configuration.
        This method attempts to use the REST API but may not be supported on all deployments.
        """
        logger.info(f"Attempting cluster recovery from '{snapshot_location}'")
        
        service = SnapshotService._create_service(url, port, https, api_key)
        base_url = service._get_base_url()
        headers = service._get_headers()
        
        payload = {"location": snapshot_location}
        if priority:
            payload["priority"] = priority
        
        try:
            response = requests.put(
                f"{base_url}/snapshots/recover",
                headers=headers,
                json=payload,
                timeout=service._snapshot_timeout
            )
            response.raise_for_status()
            logger.info("Cluster recovery initiated")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cluster recovery failed: {e}")
            raise RuntimeError(
                f"Full snapshot recovery failed. This operation may require server restart. "
                f"Error: {e}"
            )
    
    @staticmethod
    def delete_cluster_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        snapshot_name: str,
        wait: bool = True
    ) -> bool:
        """Delete a full cluster snapshot (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.delete_full_snapshot_impl(snapshot_name, wait=wait)
    
    # --- Utility Methods (Static) ---
    
    @staticmethod
    def get_collections(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str]
    ) -> List[str]:
        """Get list of collection names (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.get_collections_impl()
    
    @staticmethod
    def download_snapshot(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str,
        snapshot_name: str,
        output_path: Optional[str] = None
    ) -> str:
        """Download a collection snapshot (static method)."""
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.download_snapshot_impl(collection_name, snapshot_name, output_path)
    
    @staticmethod
    def get_snapshot_file_path(
        url: str,
        port: str,
        https: bool,
        api_key: Optional[str],
        collection_name: str,
        snapshot_name: str
    ) -> str:
        """
        Get the download URL for a snapshot.
        
        Note: This method returns a download URL, not a file path.
        For backwards compatibility, the method name is preserved.
        """
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.get_snapshot_download_url(collection_name, snapshot_name)
