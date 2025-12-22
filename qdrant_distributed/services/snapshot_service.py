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
        location_api_key: Optional[str] = None,
        force_delete_existing: bool = False,
        pre_download: bool = False,
        pre_download_path: Optional[str] = None
    ) -> bool:
        """
        Recover a collection from a snapshot.
        
        ⚠️ CRITICAL BEHAVIOR IN DISTRIBUTED QDRANT:
        - If collection EXISTS with replicas, recover_snapshot may skip actual recovery!
        - Qdrant prefers existing replicas over snapshot download for speed
        - To FORCE recovery from snapshot, you MUST delete the collection first
        
        Args:
            collection_name: Name of the collection to recover
            location: Snapshot location - can be:
                - URL to download snapshot from (http://, https://, s3://)
                - Local file path on the Qdrant server
            priority: Recovery priority (low, normal, snapshot)
                - "snapshot": Try to use snapshot (may still use replicas if available!)
                - "replica": Prefer existing replicas over snapshot
            checksum: Expected SHA-256 checksum for validation
            wait: Wait for recovery to complete (default: True)
            location_api_key: API key for accessing the snapshot location (if remote)
            force_delete_existing: If True, delete existing collection before recovery
                ⚠️ WARNING: This will DELETE the current collection!
                Only use if you're CERTAIN you want to replace existing data.
            pre_download: If True, download snapshot locally first, then use local path
                ⚡ RECOMMENDED for large snapshots (>1GB) - much faster recovery!
            pre_download_path: Local path to save snapshot (default: temp directory)
                Only used if pre_download=True
            
        Returns:
            True if recovery initiated/completed successfully
            
        Raises:
            ValueError: If collection exists and force_delete_existing=False
        """
        logger.info(
            f"Recovering collection '{collection_name}' from '{location}' "
            f"(priority={priority}, wait={wait}, force_delete={force_delete_existing}, pre_download={pre_download})"
        )
        
        # Pre-download snapshot if requested (RECOMMENDED for large snapshots)
        final_location = location
        if pre_download and (location.startswith("http://") or location.startswith("https://")):
            import tempfile
            import os
            from pathlib import Path
            
            print(f"\n📥 Pre-downloading snapshot (RECOMMENDED for faster recovery)...")
            print(f"   Source: {location}")
            
            # Determine download path
            if pre_download_path:
                download_path = pre_download_path
            else:
                # Use temp directory
                temp_dir = tempfile.gettempdir()
                # Extract filename from URL
                filename = location.split("/")[-1].split("?")[0]  # Remove query params
                if not filename or "." not in filename:
                    filename = f"snapshot_{collection_name}_{int(time.time())}.snapshot"
                download_path = os.path.join(temp_dir, filename)
            
            print(f"   Destination: {download_path}")
            
            # Download with progress
            try:
                download_start = time.time()
                response = requests.get(
                    location,
                    headers=self._get_headers() if not location_api_key else {
                        **self._get_headers(),
                        "api-key": location_api_key
                    },
                    stream=True,
                    timeout=self.DOWNLOAD_TIMEOUT
                )
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192 * 16  # 128KB chunks for faster download
                last_progress_time = download_start
                
                os.makedirs(os.path.dirname(download_path), exist_ok=True)
                
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Show progress every 2 seconds
                            now = time.time()
                            if now - last_progress_time >= 2.0:
                                elapsed_dl = now - download_start
                                speed = downloaded / elapsed_dl if elapsed_dl > 0 else 0
                                percent = (downloaded / total_size * 100) if total_size > 0 else 0
                                
                                # Format sizes
                                dl_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                                speed_mb = speed / (1024 * 1024)
                                
                                # Estimate remaining time
                                remaining = (total_size - downloaded) / speed if speed > 0 and total_size > 0 else 0
                                
                                print(f"   ⬇️  {dl_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%) | "
                                      f"Speed: {speed_mb:.2f} MB/s | "
                                      f"ETA: {int(remaining)}s", end='\r')
                                last_progress_time = now
                
                download_time = time.time() - download_start
                file_size_mb = downloaded / (1024 * 1024)
                avg_speed_mb = file_size_mb / download_time if download_time > 0 else 0
                
                print(f"\n   ✅ Downloaded {file_size_mb:.2f} MB in {int(download_time)}s "
                      f"(avg {avg_speed_mb:.2f} MB/s)")
                
                # Use absolute file path - Qdrant accepts absolute paths if accessible from server
                # Note: This works if Qdrant server can access the local filesystem
                # (same machine, shared mount, or Docker volume mount)
                if os.path.exists(download_path):
                    abs_path = os.path.abspath(download_path)
                    # Qdrant accepts absolute paths directly (no file:// prefix needed)
                    final_location = abs_path
                    print(f"   📍 Using local path: {abs_path}")
                    print(f"   ⚡ Recovery will be MUCH faster now (no network download needed)!")
                    print(f"   ⚠️  Note: Qdrant server must be able to access this path")
                    print(f"      (works if Qdrant is on same machine or shared filesystem)")
                else:
                    logger.warning(f"Downloaded file not found: {download_path}")
                    final_location = location
                    
            except Exception as e:
                logger.error(f"Pre-download failed: {e}. Falling back to direct URL recovery.")
                print(f"   ⚠️  Pre-download failed: {e}")
                print(f"   📥 Will use direct URL recovery (slower)")
                final_location = location
        
        client = self._get_client(timeout=self._snapshot_timeout)
        
        # CRITICAL: Check if collection exists
        collection_exists = False
        existing_points = 0
        initial_points_count = 0
        
        try:
            collection_info = client.get_collection(collection_name)
            collection_exists = True
            existing_points = collection_info.points_count
            initial_points_count = existing_points
            
            logger.warning(
                f"Collection '{collection_name}' already exists with {existing_points:,} points"
            )
            
            # In distributed Qdrant, recover_snapshot will likely SKIP actual recovery
            # if replicas are available, even with priority="snapshot"
            if not force_delete_existing:
                error_msg = (
                    f"Collection '{collection_name}' already exists with {existing_points:,} points. "
                    f"Set force_delete_existing=True to delete and recover from snapshot."
                )
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # User confirmed - delete existing collection
            logger.warning("force_delete_existing=True - DELETING existing collection!")
            print(f"\n⚠️  DELETING collection '{collection_name}' with {existing_points:,} points...")
            
            client.delete_collection(collection_name)
            logger.info(f"Collection '{collection_name}' deleted")
            print(f"✓ Collection deleted")
            
            # Wait for deletion to propagate across cluster
            print(f"⏳ Waiting for deletion to propagate (5 seconds)...")
            time.sleep(5)
            print(f"✓ Ready for recovery\n")
            
        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                # Collection doesn't exist - perfect!
                logger.info(f"Collection '{collection_name}' does not exist - will create from snapshot")
                collection_exists = False
            elif isinstance(e, ValueError):
                # Our own error about existing collection
                raise
            else:
                # Some other error
                logger.error(f"Error checking collection: {e}")
                raise
        
        # Convert string priority to enum if needed
        priority_value = None
        if priority:
            if isinstance(priority, str):
                priority_value = priority.lower()
            else:
                priority_value = priority.value
        
        try:
            # Now recover from snapshot
            print(f"📥 Initiating snapshot recovery...")
            print(f"📍 Location: {final_location}")
            if final_location != location:
                print(f"   (Original: {location})")
            print(f"🎯 Priority: {priority_value}")
            
            if not pre_download or not (location.startswith("http://") or location.startswith("https://")):
                print(f"\n⏳ This will:")
                print(f"   1. Download snapshot from source (may take time)")
                print(f"   2. Extract and validate snapshot")
                print(f"   3. Index all vectors")
            else:
                print(f"\n⏳ This will:")
                print(f"   1. Extract and validate snapshot (already downloaded)")
                print(f"   2. Index all vectors")
            print()
            
            # Use direct REST API for better control over wait=false and api_key handling
            # This avoids gateway timeouts and properly handles authenticated snapshot URLs
            protocol = "https" if self._https else "http"
            base_url = f"{protocol}://{self._url}:{self._port}"
            recover_url = f"{base_url}/collections/{collection_name}/snapshots/recover?wait=false"
            
            payload = {
                "location": final_location,
            }
            
            if priority_value:
                payload["priority"] = priority_value
            
            if checksum:
                payload["checksum"] = checksum
            
            # Pass API key for authenticated snapshot downloads (e.g., from authenticated Qdrant servers)
            if location_api_key:
                payload["api_key"] = location_api_key
            
            headers = self._get_headers()
            
            logger.info(f"Sending recovery request to {recover_url}")
            response = requests.put(recover_url, json=payload, headers=headers, timeout=30)
            
            if not response.ok:
                error_msg = f"Recovery request failed: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            response.raise_for_status()
            
            print(f"✓ Recovery request sent to Qdrant (running in background)")
            logger.info("Recovery request submitted successfully")
            
            if wait:
                print(f"\n📊 Monitoring recovery progress...")
                logger.info(f"Monitoring collection '{collection_name}' recovery...")
                start_time = time.time()
                last_log_time = start_time
                last_points = 0
                last_points_time = start_time
                poll_count = 0
                download_phase = True
                indexing_phase = False
                no_progress_count = 0
                collection_appeared = False
                
                while True:
                    elapsed = time.time() - start_time
                    
                    # Check timeout
                    if elapsed > self._snapshot_timeout:
                        raise TimeoutError(
                            f"Timed out waiting for collection '{collection_name}' recovery "
                            f"after {self._snapshot_timeout} seconds ({self._snapshot_timeout/60:.0f} minutes)"
                        )
                    
                    try:
                        # Get collection status (may 404 during download phase - this is NORMAL)
                        check_client = self._get_client(timeout=10)
                        collection_info = check_client.get_collection(collection_name)
                        
                        # Collection exists now!
                        if not collection_appeared:
                            collection_appeared = True
                            download_phase = False
                            print(f"\n✅ Collection appeared! Server completed download & extraction")
                        
                        status = collection_info.status
                        points = collection_info.points_count
                        
                        # Handle status check
                        status_str = str(status.value if hasattr(status, 'value') else status).lower()
                        
                        # Detect phase transitions
                        if download_phase and points > 0:
                            download_phase = False
                            indexing_phase = True
                            print(f"\n✓ Download complete! Indexing started...")
                            print(f"📊 Points appearing: {points:,}")
                        
                        # Track point growth to detect server activity
                        points_growth = points - last_points
                        if points_growth > 0:
                            no_progress_count = 0  # Reset
                            time_since_last_growth = elapsed - last_points_time
                            growth_rate = points_growth / time_since_last_growth if time_since_last_growth > 0 else 0
                            last_points = points
                            last_points_time = elapsed
                        else:
                            no_progress_count += 1
                        
                        # Log progress every 15 seconds (more frequent for large files)
                        if elapsed - last_log_time >= 15:
                            if indexing_phase:
                                # Show indexing progress with growth rate
                                points_per_sec = points / elapsed if elapsed > 0 else 0
                                
                                # Build progress message
                                progress_msg = f"📊 Status: {status_str.upper()} | Points: {points:,}"
                                
                                if points_per_sec > 0:
                                    progress_msg += f" | Rate: {points_per_sec:,.0f}/sec"
                                    
                                    # Estimate remaining time if we're not green yet
                                    if status_str in ["yellow", "red"]:
                                        # Rough estimate: assume we need 2-3x current points
                                        estimated_total_points = points * 2.5
                                        remaining_points = max(0, estimated_total_points - points)
                                        remaining_sec = remaining_points / points_per_sec if points_per_sec > 0 else 0
                                        progress_msg += f" | Est. ~{int(remaining_sec/60)}m left"
                                
                                progress_msg += f" | Elapsed: {int(elapsed/60)}m"
                                print(progress_msg)
                                
                                # Warn if no progress
                                if no_progress_count > 4:  # No growth for 20+ seconds
                                    print(f"   ⚠️  No new points for {no_progress_count * 5}s - server may be processing...")
                            else:
                                # Still in download phase
                                print(f"⏳ Status: {status_str.upper()} | Points: {points:,} | Elapsed: {int(elapsed/60)}m")
                            
                            last_log_time = elapsed
                        
                        if status_str == "green":
                            print(f"\n✅ Collection '{collection_name}' recovered successfully!")
                            print(f"📊 Final points: {points:,}")
                            print(f"⏱️  Total time: {int(elapsed)} seconds ({elapsed/60:.1f} minutes)\n")
                            
                            # CRITICAL CHECK: Did recovery actually happen?
                            if collection_exists and points == existing_points and elapsed < 5:
                                logger.error(
                                    f"SUSPICIOUS: Collection recovered in {elapsed}s with same point count! "
                                    f"Recovery may have been skipped!"
                                )
                                print(f"⚠️  WARNING: Recovery completed suspiciously fast ({elapsed}s)")
                                print(f"⚠️  Points unchanged: {points:,}")
                                print(f"⚠️  This suggests Qdrant used existing replicas instead of snapshot!")
                                print(f"⚠️  Verify the data is actually from the snapshot!\n")
                            
                            logger.info(f"Collection '{collection_name}' is ready (status: GREEN)")
                            break
                        
                        logger.debug(f"Collection status: {status_str}, points: {points}")
                        poll_count += 1
                             
                    except Exception as e:
                        # Collection doesn't exist yet - server is downloading/extracting (this is NORMAL)
                        # We expect 404s during this phase - don't spam the server!
                        error_msg = str(e)
                        
                        # Only log at DEBUG level to avoid noise
                        if "not found" in error_msg.lower() or "doesn't exist" in error_msg.lower():
                            logger.debug(f"Collection not found yet (download phase) - poll #{poll_count}")
                        else:
                            logger.debug(f"Polling check #{poll_count} failed: {error_msg}")
                        
                        # Active download monitoring
                        if poll_count == 1:
                            print(f"\n🔄 Server-side download started")
                            if final_location.startswith("http://") or final_location.startswith("https://"):
                                print(f"📥 Qdrant server is downloading from: {final_location}")
                                print(f"⏳ This may take time depending on file size and network speed")
                                print(f"💡 Collection will appear once download completes and extraction starts")
                            else:
                                print(f"📁 Qdrant server is loading from: {final_location}")
                        
                        # Show regular heartbeat to prove we're monitoring (but not too often!)
                        elif elapsed - last_log_time >= 30:  # Every 30 seconds (reduced to avoid log spam)
                            elapsed_min = elapsed / 60
                            
                            # Check if server is still alive and responding (use lightweight endpoint)
                            server_alive = False
                            try:
                                # Use get_collections() instead of get_collection() to avoid 404 spam
                                check_client.get_collections()
                                server_alive = True
                            except:
                                pass
                            
                            if server_alive:
                                # Server is responding - download/processing is happening
                                if final_location.startswith("http://") or final_location.startswith("https://"):
                                    print(f"📥 DOWNLOADING: {int(elapsed)}s ({elapsed_min:.1f}m) - Server is actively downloading...")
                                else:
                                    print(f"⚙️  PROCESSING: {int(elapsed)}s ({elapsed_min:.1f}m) - Server is extracting...")
                            else:
                                print(f"⚠️  WARNING: {int(elapsed)}s ({elapsed_min:.1f}m) - Server not responding!")
                            
                            last_log_time = elapsed
                        
                        # Provide detailed status after some time
                        if elapsed > 300 and poll_count % 20 == 0:  # Every 100 seconds after 5 minutes
                            elapsed_min = elapsed / 60
                            print(f"\n📊 Status Report ({elapsed_min:.1f} minutes elapsed):")
                            
                            # Check server health
                            try:
                                check_client.get_collections()
                                print(f"   ✅ Qdrant server is RESPONDING (download/processing is active)")
                            except Exception as health_err:
                                print(f"   ❌ Qdrant server NOT responding: {health_err}")
                                print(f"   🔴 Recovery may have FAILED!")
                            
                            # Provide context based on location type
                            if final_location.startswith("http://") or final_location.startswith("https://"):
                                if not pre_download:
                                    print(f"   📥 Server is downloading from remote URL")
                                    print(f"   💡 TIP: Next time use pre_download=True for faster recovery!")
                                    print(f"   ⏱️  Large files (7GB+) can take 15-60+ minutes to download")
                                else:
                                    print(f"   📁 Using pre-downloaded local file (faster!)")
                                    print(f"   ⚙️  Server is extracting and indexing")
                            else:
                                print(f"   📁 Server is processing local snapshot")
                                print(f"   ⚙️  Extracting and indexing vectors")
                            
                            print(f"   📌 Check server logs: docker logs <container> | grep -i snapshot")
                            print(f"   📌 Collection will appear once first vectors are indexed")
                            print()
                        
                        # Critical alert after very long wait
                        if elapsed > 1800 and poll_count % 24 == 0:  # Every 2 minutes after 30 min
                            print(f"\n🔴 ALERT: {int(elapsed/60)} minutes elapsed, collection still not appearing!")
                            print(f"\n🔍 Diagnostic checks:")
                            print(f"   1. Verify Qdrant server can reach URL:")
                            print(f"      curl -I '{final_location}'")
                            print(f"   2. Check Qdrant server logs:")
                            print(f"      docker logs <container> -f | grep -i snapshot")
                            print(f"   3. Check disk space:")
                            print(f"      df -h (server needs 2x snapshot size)")
                            print(f"   4. Check server is not OOM killed:")
                            print(f"      dmesg | grep -i oom")
                            print()
                    
                    poll_count += 1
                    
                    # Adaptive poll interval: longer during download phase to reduce log spam
                    if not collection_appeared:
                        # During download phase: poll every 20 seconds (collection doesn't exist yet)
                        time.sleep(20)
                    else:
                        # During indexing phase: poll every 5 seconds (monitoring point growth)
                        time.sleep(5)

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
        location_api_key: Optional[str] = None,
        force_delete_existing: bool = False,
        pre_download: bool = False,
        pre_download_path: Optional[str] = None
    ) -> bool:
        """
        Recover a collection from snapshot (static method).
        
        ⚠️ IMPORTANT: In distributed Qdrant clusters, if the collection already exists,
        recovery may be skipped even with priority="snapshot"! Set force_delete_existing=True
        to delete and recreate the collection.
        
        ⚡ PERFORMANCE TIP: For large snapshots (>1GB), set pre_download=True!
        This downloads the snapshot locally first, then uses local path for recovery.
        This is MUCH faster than letting Qdrant download from URL.
        
        Args:
            url: Qdrant server URL
            port: Qdrant server port
            https: Use HTTPS
            api_key: Qdrant API key
            collection_name: Collection to recover
            snapshot_location: URL or path to snapshot
            priority: Recovery priority ("snapshot" or "replica")
            checksum: Expected SHA-256 checksum
            wait: Wait for completion
            location_api_key: API key for snapshot location
            force_delete_existing: Delete existing collection before recovery (DANGEROUS!)
            pre_download: Pre-download snapshot locally first (RECOMMENDED for >1GB)
            pre_download_path: Local path to save snapshot (default: temp directory)
        """
        service = SnapshotService._create_service(url, port, https, api_key)
        return service.recover_collection_snapshot_impl(
            collection_name=collection_name,
            location=snapshot_location,
            priority=priority,
            checksum=checksum,
            wait=wait,
            location_api_key=location_api_key,
            force_delete_existing=force_delete_existing,
            pre_download=pre_download,
            pre_download_path=pre_download_path
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
