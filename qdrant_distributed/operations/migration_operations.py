"""
Migration Operations - High-level facade for migration operations.
"""

from typing import Dict, Any, Optional, Callable
import asyncio
import logging

from qdrant_distributed.services.migration_service import (
    MultiQdrantManager,
    migrate_all,
    migrate_with_checks,
    check_collections_sync,
    ensure_collection_exists
)

logger = logging.getLogger(__name__)


class MigrationOperations:
    """
    High-level facade for migration operations.
    
    This class provides a simplified interface for Qdrant collection migration,
    abstracting away the underlying service layer complexity.
    """
    
    def __init__(self):
        """Initialize migration operations."""
        pass
    
    async def migrate_all(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        mysql_config: Optional[Dict[str, Any]] = None,
        reverse: bool = False,
        progress_callback: Optional[Callable] = None,
        embedding_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        cancellation_flag: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Migrate all collections from source to target Qdrant instance.
        
        Args:
            source_config: Source Qdrant configuration dict with keys:
                - url: Qdrant URL
                - port: Qdrant port
                - api_key: Optional API key
                - https: Optional HTTPS flag
            target_config: Target Qdrant configuration dict (same structure)
            mysql_config: Optional MySQL configuration dict
            reverse: If True, reverse migration direction
            progress_callback: Optional callback for progress updates (collection_id, current, total)
            embedding_callback: Optional async callback for generating embeddings
        
        Returns:
            Dictionary with migration results:
                - total_documents: Total documents migrated
                - successful_collections: List of successfully migrated collections
                - failed_collections: List of failed collection IDs
                - total_collections: Total number of collections
        """
        try:
            # Initialize MySQL - use provided config or default
            from qdrant_distributed.config import MySQLManager
            if mysql_config:
                MySQLManager.initialize(
                    host=mysql_config.get('host'),
                    port=mysql_config.get('port'),
                    user=mysql_config.get('user'),
                    password=mysql_config.get('password'),
                    database=mysql_config.get('database')
                )
            else:
                # Use default MySQL config from ConfigService/environment
                MySQLManager.initialize()
            
            # Create Qdrant manager
            https = source_config.get('https', False) or target_config.get('https', False)
            qdrant_manager = MultiQdrantManager(https=https)
            
            # Determine source and target based on reverse flag
            if reverse:
                # Reverse: target becomes source, source becomes target
                source_qdrant = target_config
                target_qdrant = source_config
            else:
                source_qdrant = source_config
                target_qdrant = target_config
            
            # Add source client (default)
            qdrant_manager.add_client(
                name='default',
                url=source_qdrant['url'],
                port=source_qdrant['port'],
                api_key=source_qdrant.get('api_key'),
                https=source_qdrant.get('https', False)
            )
            
            qdrant_manager.add_async_client(
                name='default_async',
                url=source_qdrant['url'],
                port=source_qdrant['port'],
                api_key=source_qdrant.get('api_key'),
                https=source_qdrant.get('https', False)
            )
            
            # Add target client (distributed)
            qdrant_manager.add_client(
                name='distributed',
                url=target_qdrant['url'],
                port=target_qdrant['port'],
                api_key=target_qdrant.get('api_key'),
                https=target_qdrant.get('https', False)
            )
            
            qdrant_manager.add_async_client(
                name='distributed_async',
                url=target_qdrant['url'],
                port=target_qdrant['port'],
                api_key=target_qdrant.get('api_key'),
                https=target_qdrant.get('https', False)
            )
            
            # Ensure collections exist
            try:
                from qdrant_distributed.constant import SHARED_COLLECTION_NAME
                source_async = qdrant_manager.get_async_client('default_async')
                target_async = qdrant_manager.get_async_client('distributed_async')
                
                # First verify source collection exists (we need it to copy config from)
                try:
                    await source_async.get_collection(SHARED_COLLECTION_NAME)
                except Exception as e:
                    error_msg = f"Source collection '{SHARED_COLLECTION_NAME}' does not exist. Cannot migrate."
                    logger.error(error_msg)
                    raise ValueError(error_msg) from e
                
                # Ensure target collection exists, creating it from source config if needed
                await ensure_collection_exists(target_async, SHARED_COLLECTION_NAME, source_client=source_async)
                
                # Wait a moment for collections to be available
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Error ensuring collections exist: {e}")
                # Continue anyway - collection might already exist
            
            # Perform migration
            result = await migrate_all(
                qdrant_manager,
                progress_callback=progress_callback,
                embedding_callback=embedding_callback,
                status_callback=status_callback,
                cancellation_flag=cancellation_flag
            )
            
            # Cleanup
            qdrant_manager.close_all()
            await qdrant_manager.close_async_clients()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in migrate_all: {e}")
            raise
    
    async def migrate_with_checks(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        mysql_config: Optional[Dict[str, Any]] = None,
        reverse: bool = False,
        progress_callback: Optional[Callable] = None,
        embedding_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        cancellation_flag: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Migrate only missing documents after checking synchronization.
        
        Args:
            source_config: Source Qdrant configuration dict
            target_config: Target Qdrant configuration dict
            mysql_config: Optional MySQL configuration dict
            reverse: If True, reverse migration direction
            progress_callback: Optional callback for progress updates
            embedding_callback: Optional async callback for generating embeddings
        
        Returns:
            Dictionary with migration results
        """
        try:
            # Initialize MySQL - use provided config or default
            from qdrant_distributed.config import MySQLManager
            if mysql_config:
                MySQLManager.initialize(
                    host=mysql_config.get('host'),
                    port=mysql_config.get('port'),
                    user=mysql_config.get('user'),
                    password=mysql_config.get('password'),
                    database=mysql_config.get('database')
                )
            else:
                # Use default MySQL config from ConfigService/environment
                MySQLManager.initialize()
            
            # Create Qdrant manager
            https = source_config.get('https', False) or target_config.get('https', False)
            qdrant_manager = MultiQdrantManager(https=https)
            
            # Determine source and target
            if reverse:
                source_qdrant = target_config
                target_qdrant = source_config
            else:
                source_qdrant = source_config
                target_qdrant = target_config
            
            # Add clients
            qdrant_manager.add_client(
                name='default',
                url=source_qdrant['url'],
                port=source_qdrant['port'],
                api_key=source_qdrant.get('api_key'),
                https=source_qdrant.get('https', False)
            )
            
            qdrant_manager.add_async_client(
                name='default_async',
                url=source_qdrant['url'],
                port=source_qdrant['port'],
                api_key=source_qdrant.get('api_key'),
                https=source_qdrant.get('https', False)
            )
            
            qdrant_manager.add_client(
                name='distributed',
                url=target_qdrant['url'],
                port=target_qdrant['port'],
                api_key=target_qdrant.get('api_key'),
                https=target_qdrant.get('https', False)
            )
            
            qdrant_manager.add_async_client(
                name='distributed_async',
                url=target_qdrant['url'],
                port=target_qdrant['port'],
                api_key=target_qdrant.get('api_key'),
                https=target_qdrant.get('https', False)
            )
            
            # Ensure collections exist
            try:
                from qdrant_distributed.constant import SHARED_COLLECTION_NAME
                source_async = qdrant_manager.get_async_client('default_async')
                target_async = qdrant_manager.get_async_client('distributed_async')
                
                # First verify source collection exists (we need it to copy config from)
                try:
                    await source_async.get_collection(SHARED_COLLECTION_NAME)
                except Exception as e:
                    error_msg = f"Source collection '{SHARED_COLLECTION_NAME}' does not exist. Cannot migrate."
                    logger.error(error_msg)
                    raise ValueError(error_msg) from e
                
                # Ensure target collection exists, creating it from source config if needed
                await ensure_collection_exists(target_async, SHARED_COLLECTION_NAME, source_client=source_async)
                
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Error ensuring collections exist: {e}")
            
            # Perform migration with checks
            result = await migrate_with_checks(
                qdrant_manager,
                progress_callback=progress_callback,
                embedding_callback=embedding_callback,
                status_callback=status_callback,
                cancellation_flag=cancellation_flag
            )
            
            # Cleanup
            qdrant_manager.close_all()
            await qdrant_manager.close_async_clients()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in migrate_with_checks: {e}")
            raise
    
    async def check_sync(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        mysql_config: Optional[Dict[str, Any]] = None,
        check_count: bool = True,
        cancellation_flag: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Check synchronization between source and target Qdrant instances.
        
        Args:
            source_config: Source Qdrant configuration dict
            target_config: Target Qdrant configuration dict
            mysql_config: Optional MySQL configuration dict
            check_count: Whether to check document counts
        
        Returns:
            Dictionary with sync check results
        """
        try:
            # Initialize MySQL - use provided config or default
            from qdrant_distributed.config import MySQLManager
            if mysql_config:
                MySQLManager.initialize(
                    host=mysql_config.get('host'),
                    port=mysql_config.get('port'),
                    user=mysql_config.get('user'),
                    password=mysql_config.get('password'),
                    database=mysql_config.get('database')
                )
            else:
                # Use default MySQL config from ConfigService/environment
                MySQLManager.initialize()
            
            # Create Qdrant manager
            https = source_config.get('https', False) or target_config.get('https', False)
            qdrant_manager = MultiQdrantManager(https=https)
            
            # Add clients
            qdrant_manager.add_client(
                name='default',
                url=source_config['url'],
                port=source_config['port'],
                api_key=source_config.get('api_key'),
                https=source_config.get('https', False)
            )
            
            qdrant_manager.add_client(
                name='distributed',
                url=target_config['url'],
                port=target_config['port'],
                api_key=target_config.get('api_key'),
                https=target_config.get('https', False)
            )
            
            # Perform sync check
            result = await check_collections_sync(qdrant_manager, check_count=check_count,
                                                 cancellation_flag=cancellation_flag)
            
            # Cleanup
            qdrant_manager.close_all()
            await qdrant_manager.close_async_clients()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in check_sync: {e}")
            raise

