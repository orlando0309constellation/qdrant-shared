"""
Migration Controller - Handles execution of migration operations.
"""

import asyncio
import threading
import multiprocessing
import logging
import sys
from typing import Dict, Any, Optional
from tkinter import messagebox

from qdrant_distributed.operations.migration_operations import MigrationOperations

logger = logging.getLogger(__name__)

# Set multiprocessing start method for Windows and built applications
if sys.platform == 'win32':
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        # Already set, ignore
        pass


def _execute_migration_process(
    queue: multiprocessing.Queue,
    source_config: Dict[str, Any],
    target_config: Dict[str, Any],
    mysql_config: Optional[Dict[str, Any]],
    mode: str,
    reverse: bool,
    enable_ai: bool = True
):
    """Standalone function to execute migration in a separate process."""
    try:
        from qdrant_distributed.services.migration_service import add_log_callback
        from qdrant_distributed.operations.migration_operations import MigrationOperations
        
        migration_ops = MigrationOperations()
        
        def emit(event: str, *args, **kwargs):
            """Send event to main process via queue."""
            queue.put(('event', event, args, kwargs))
        
        # Register log callback
        def log_callback(message: str, level: str = "info"):
            tag_map = {
                "debug": None,
                "info": "info",
                "warning": "warning",
                "error": "error",
                "critical": "error"
            }
            tag = tag_map.get(level.lower(), "info")
            emit("log_output", message + "\n", tag)
        
        add_log_callback(log_callback)
        
        # Status callback
        def status_callback(collection_id: str, status: str, missing: int = 0,
                           migrated: int = 0, total: int = 0, current_batch: int = 0,
                           state: str = "", total_batches: int = 0):
            emit("collection_status", collection_id, status, missing, migrated, total, current_batch, state, total_batches)
        
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Log configuration
        source_url_display = f"{source_config.get('url', 'N/A')}:{source_config.get('port', 'N/A')}"
        target_url_display = f"{target_config.get('url', 'N/A')}:{target_config.get('port', 'N/A')}"
        mysql_display = "default (ours)" if mysql_config is None else f"{mysql_config.get('host', 'N/A')}:{mysql_config.get('port', 'N/A')}"
        
        emit("log_output", f"🚀 Starting migration in {mode} mode\n", "header")
        emit("log_output", f"Configuration:\n", "info")
        emit("log_output", f"  Source Qdrant: {source_url_display} (HTTPS: {source_config.get('https', False)})\n", "info")
        emit("log_output", f"  Target Qdrant: {target_url_display} (HTTPS: {target_config.get('https', False)})\n", "info")
        emit("log_output", f"  MySQL Source: {mysql_display}\n", "info")
        emit("log_output", f"  Reverse Mode: {reverse}\n", "info")
        emit("log_output", f"  AI Summaries: {'Enabled' if enable_ai else 'Disabled'}\n", "info")
        emit("log_output", f"\n", "info")
        emit("progress_update", 5, "Initializing migration...")
        
        # Set embedding_callback to None when AI is disabled
        embedding_callback = None if not enable_ai else None  # Currently always None, but explicit for future use
        
        # Progress callback
        def progress_callback(collection_id: str, current: int, total: Optional[int]):
            if total:
                percentage = int((current / total) * 100)
                emit("progress_update", percentage, f"Processing {collection_id}: {current}/{total}")
                emit("collection_status", collection_id, "Processing", 
                      missing=total - current, migrated=current, total=total,
                      current_batch=current, state=f"Migrating... {percentage}%")
            else:
                emit("log_output", f"  Collection {collection_id}: {current} documents processed\n", "info")
                emit("collection_status", collection_id, "Processing",
                      missing=0, migrated=current, total=0,
                      current_batch=current, state="Processing...")
        
        # Check for cancellation flag via queue
        def check_cancellation():
            try:
                # Non-blocking check
                while not queue.empty():
                    item = queue.get_nowait()
                    if item[0] == 'cancel':
                        return True
                    # Put it back if it's not a cancel message
                    queue.put(item)
            except:
                pass
            return False
        
        # Execute based on mode
        if mode == "migrate":
            emit("log_output", "🔄 Running in MIGRATE mode - migrating all collections\n", "info")
            emit("progress_update", 10, "Starting migration...")
            
            try:
                result = loop.run_until_complete(
                    migration_ops.migrate_all(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        reverse=reverse,
                        progress_callback=progress_callback,
                        embedding_callback=embedding_callback,
                        status_callback=status_callback,
                        cancellation_flag=check_cancellation
                    )
                )
            except asyncio.CancelledError:
                emit("log_output", "\n❌ Migration cancelled\n", "warning")
                return
            
            # Update final status
            for coll in result.get('successful_collections', []):
                emit("collection_status", coll['id'], "Completed",
                      missing=0, migrated=coll.get('documents', 0), 
                      total=coll.get('documents', 0), current_batch=0,
                      state="✅ Completed")
            
            for coll_id in result.get('failed_collections', []):
                emit("collection_status", coll_id, "Failed",
                      missing=0, migrated=0, total=0, current_batch=0,
                      state="❌ Failed")
            
            emit("log_output", f"\n✅ Migration completed!\n", "success")
            emit("log_output", f"Total documents migrated: {result['total_documents']}\n", "info")
            emit("log_output", f"Successful collections: {len(result['successful_collections'])}\n", "success")
            if result['failed_collections']:
                emit("log_output", f"Failed collections: {result['failed_collections']}\n", "error")
        
        elif mode == "migrate-usc":
            emit("log_output", "🔍 Running in MIGRATE-USC mode - migrating only missing documents\n", "info")
            emit("progress_update", 10, "Checking synchronization...")
            
            try:
                result = loop.run_until_complete(
                    migration_ops.migrate_with_checks(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        reverse=reverse,
                        progress_callback=progress_callback,
                        embedding_callback=embedding_callback,
                        status_callback=status_callback,
                        cancellation_flag=check_cancellation
                    )
                )
            except asyncio.CancelledError:
                emit("log_output", "\n❌ Migration cancelled\n", "warning")
                return
            
            # Update final status
            for coll in result.get('successful_collections', []):
                emit("collection_status", coll['id'], "Completed",
                      missing=0, migrated=coll.get('documents', 0),
                      total=coll.get('documents', 0), current_batch=0,
                      state="✅ Completed")
            
            for coll_id in result.get('failed_collections', []):
                emit("collection_status", coll_id, "Failed",
                      missing=0, migrated=0, total=0, current_batch=0,
                      state="❌ Failed")
            
            emit("log_output", f"\n✅ Selective migration completed!\n", "success")
            emit("log_output", f"Total documents migrated: {result['total_documents']}\n", "info")
            emit("log_output", f"Already synchronized: {result.get('already_synced', 0)} collections\n", "info")
            emit("log_output", f"Successful collections: {len(result['successful_collections'])}\n", "success")
            if result['failed_collections']:
                emit("log_output", f"Failed collections: {result['failed_collections']}\n", "error")
        
        elif mode == "check":
            emit("log_output", "🔍 Running in CHECK mode - verifying synchronization\n", "info")
            emit("progress_update", 10, "Checking synchronization...")
            
            try:
                result = loop.run_until_complete(
                    migration_ops.check_sync(
                        source_config=source_config,
                        target_config=target_config,
                        mysql_config=mysql_config,
                        check_count=True,
                        cancellation_flag=check_cancellation
                    )
                )
            except asyncio.CancelledError:
                emit("log_output", "\n❌ Migration cancelled\n", "warning")
                return
            
            emit("log_output", f"\n📊 Synchronization Check Summary\n", "header")
            emit("log_output", f"Total collections: {result['total_collections']}\n", "info")
            emit("log_output", f"Synchronized collections: {len(result['synced_collections'])}\n", "success")
            if result['collections_with_missing_points']:
                emit("log_output", f"Collections with missing points: {len(result['collections_with_missing_points'])}\n", "warning")
                emit("log_output", f"Total missing points: {result['total_missing_points']}\n", "warning")
                for item in result['collections_with_missing_points']:
                    emit("log_output", 
                          f"  - {item['collection_id']}: {item['missing_points']} missing "
                          f"(source: {item['source_count']}, target: {item['target_count']})\n", 
                          "warning")
            if result['missing_collections']:
                emit("log_output", f"Collections with errors: {result['missing_collections']}\n", "error")
        
        emit("progress_update", 100, "Migration completed!")
        emit("log_output", "\n" + "=" * 80 + "\n", "header")
        emit("log_output", "✨ Operation completed successfully\n", "success")
        emit("log_output", "=" * 80 + "\n", "header")
        emit("status_update", "Migration completed successfully")
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.exception("Migration error")
        queue.put(('event', 'log_output', (f"\n❌ Error: {error_msg}\n", "error"), {}))
        queue.put(('event', 'status_update', (f"Error: {error_msg}",), {}))
        queue.put(('event', 'error', (error_msg,), {}))
    finally:
        queue.put(('event', 'migration_complete', (), {}))


class MigrationController:
    """Handles execution of migration operations."""
    
    def __init__(self):
        self.migration_ops = MigrationOperations()
        self._callbacks = {}
        self._is_running = False
        self._should_cancel = False
        self._migration_process = None
        self._migration_thread = None  # Keep for compatibility
        self._migration_loop = None
        self._migration_task = None
        self._queue = None
        self._queue_thread = None
    
    def register_callback(self, event: str, callback):
        """Register a callback for migration events."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _emit(self, event: str, *args, **kwargs):
        """Emit an event to registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Error in callback for event {event}: {e}")
    
    def is_running(self) -> bool:
        """Check if migration is currently running."""
        return self._is_running
    
    def cancel(self):
        """Cancel the running migration by terminating the process."""
        if not self._is_running:
            return
        
        logger.info("Cancellation requested - terminating migration process")
        self._should_cancel = True
        self._emit("log_output", "\n⚠️ Migration cancellation requested...\n", "warning")
        
        # Send cancel signal via queue
        if self._queue:
            try:
                self._queue.put(('cancel',))
            except:
                pass
        
        # Forcefully terminate the migration process
        if self._migration_process and self._migration_process.is_alive():
            try:
                self._migration_process.terminate()
                logger.info("Terminated migration process")
                # Wait a bit for it to terminate
                self._migration_process.join(timeout=2)
                if self._migration_process.is_alive():
                    # Force kill if still alive
                    self._migration_process.kill()
                    self._migration_process.join()
                    logger.warning("Force killed migration process")
            except Exception as e:
                logger.warning(f"Error terminating process: {e}")
        
        # Emit migration_complete to re-enable the execute button
        # Process the queue one more time to get any pending messages
        if self._queue_thread and self._queue_thread.is_alive():
            # Give it a moment to process any remaining messages
            import time
            time.sleep(0.1)
        
        # Clean up and emit migration_complete
        self._is_running = False
        self._should_cancel = False
        self._migration_task = None
        self._migration_loop = None
        self._migration_process = None
        self._migration_thread = None
        self._queue = None
        self._queue_thread = None
        self._emit("migration_complete")
    
    def execute_migration(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        mysql_config: Optional[Dict[str, Any]],
        mode: str,
        reverse: bool = False,
        https: bool = True,
        enable_ai: bool = True
    ):
        """
        Execute migration in a separate thread.
        
        Args:
            source_config: Source Qdrant configuration
            target_config: Target Qdrant configuration
            mysql_config: MySQL configuration (None to use default)
            mode: Migration mode ('migrate', 'migrate-usc', 'check')
            reverse: Reverse migration direction
            https: Use HTTPS
            enable_ai: Enable AI-generated summaries (default: True)
        """
        if self._is_running:
            messagebox.showwarning("Migration Running", "A migration is already in progress.")
            return
        
        # Reset cancellation flag
        self._should_cancel = False
        
        # Update configs with HTTPS
        source_config['https'] = https
        target_config['https'] = https
        
        self._is_running = True
        self._emit("migration_start")
        
        # Create queue for inter-process communication
        # Use context manager for proper multiprocessing setup in built apps
        ctx = multiprocessing.get_context('spawn')
        self._queue = ctx.Queue()
        
        # Start thread to process queue messages
        self._queue_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self._queue_thread.start()
        
        # Use Process instead of Thread for forceful cancellation
        # Use context manager for proper multiprocessing setup in built apps
        self._migration_process = ctx.Process(
            target=_execute_migration_process,
            args=(self._queue, source_config, target_config, mysql_config, mode, reverse, enable_ai),
            daemon=True
        )
        self._migration_process.start()
        # Keep thread reference for compatibility
        self._migration_thread = self._migration_process
    
    def _process_queue(self):
        """Process messages from the migration process queue."""
        while self._is_running:
            try:
                item = self._queue.get(timeout=0.1)
                if item[0] == 'event':
                    event, args, kwargs = item[1], item[2], item[3]
                    self._emit(event, *args, **kwargs)
            except:
                continue
    
    def _execute_migration_thread(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        mysql_config: Optional[Dict[str, Any]],
        mode: str,
        reverse: bool
    ):
        """Execute migration in background thread."""
        try:
            # Register log callback to forward service logs to UI
            from qdrant_distributed.services.migration_service import add_log_callback
            
            def log_callback(message: str, level: str = "info"):
                """Forward log messages from migration service to UI."""
                # Map log levels to UI tags
                tag_map = {
                    "debug": None,  # Debug logs without special tag
                    "info": "info",
                    "warning": "warning",
                    "error": "error",
                    "critical": "error"
                }
                tag = tag_map.get(level.lower(), "info")
                self._emit("log_output", message + "\n", tag)
            
            add_log_callback(log_callback)
            
            # Status callback for collection updates
            def status_callback(collection_id: str, status: str, missing: int = 0,
                               migrated: int = 0, total: int = 0, current_batch: int = 0,
                               state: str = "", total_batches: int = 0):
                """Forward collection status updates to UI."""
                self._emit("collection_status", collection_id, status, missing, migrated, total, current_batch, state, total_batches)
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._migration_loop = loop
            
            # Log configuration (sanitized)
            source_url_display = f"{source_config.get('url', 'N/A')}:{source_config.get('port', 'N/A')}"
            target_url_display = f"{target_config.get('url', 'N/A')}:{target_config.get('port', 'N/A')}"
            mysql_display = "default (ours)" if mysql_config is None else f"{mysql_config.get('host', 'N/A')}:{mysql_config.get('port', 'N/A')}"
            
            self._emit("log_output", f"🚀 Starting migration in {mode} mode\n", "header")
            self._emit("log_output", f"Configuration:\n", "info")
            self._emit("log_output", f"  Source Qdrant: {source_url_display} (HTTPS: {source_config.get('https', False)})\n", "info")
            self._emit("log_output", f"  Target Qdrant: {target_url_display} (HTTPS: {target_config.get('https', False)})\n", "info")
            self._emit("log_output", f"  MySQL Source: {mysql_display}\n", "info")
            self._emit("log_output", f"  Reverse Mode: {reverse}\n", "info")
            self._emit("log_output", f"\n", "info")
            self._emit("progress_update", 5, "Initializing migration...")
            
            # Progress callback
            def progress_callback(collection_id: str, current: int, total: Optional[int]):
                if total:
                    percentage = int((current / total) * 100)
                    self._emit("progress_update", percentage, f"Processing {collection_id}: {current}/{total}")
                    # Update collection status
                    self._emit("collection_status", collection_id, "Processing", 
                              missing=total - current, migrated=current, total=total,
                              current_batch=current, state=f"Migrating... {percentage}%")
                else:
                    self._emit("log_output", f"  Collection {collection_id}: {current} documents processed\n", "info")
                    # Update collection status
                    self._emit("collection_status", collection_id, "Processing",
                              missing=0, migrated=current, total=0,
                              current_batch=current, state="Processing...")
            
            # Execute based on mode
            if mode == "migrate":
                if self._should_cancel:
                    self._emit("log_output", "❌ Migration cancelled by user\n", "warning")
                    return
                
                self._emit("log_output", "🔄 Running in MIGRATE mode - migrating all collections\n", "info")
                self._emit("progress_update", 10, "Starting migration...")
                
                try:
                    result = loop.run_until_complete(
                        self.migration_ops.migrate_all(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            reverse=reverse,
                            progress_callback=progress_callback,
                            status_callback=status_callback,
                            cancellation_flag=lambda: self._should_cancel
                        )
                    )
                except asyncio.CancelledError:
                    self._emit("log_output", "\n❌ Migration cancelled\n", "warning")
                    return
                
                # Update final status for all collections
                for coll in result.get('successful_collections', []):
                    self._emit("collection_status", coll['id'], "Completed",
                              missing=0, migrated=coll.get('documents', 0), 
                              total=coll.get('documents', 0), current_batch=0,
                              state="✅ Completed")
                
                for coll_id in result.get('failed_collections', []):
                    self._emit("collection_status", coll_id, "Failed",
                              missing=0, migrated=0, total=0, current_batch=0,
                              state="❌ Failed")
                
                self._emit("log_output", f"\n✅ Migration completed!\n", "success")
                self._emit("log_output", f"Total documents migrated: {result['total_documents']}\n", "info")
                self._emit("log_output", f"Successful collections: {len(result['successful_collections'])}\n", "success")
                if result['failed_collections']:
                    self._emit("log_output", f"Failed collections: {result['failed_collections']}\n", "error")
                
            elif mode == "migrate-usc":
                if self._should_cancel:
                    self._emit("log_output", "❌ Migration cancelled by user\n", "warning")
                    return
                
                self._emit("log_output", "🔍 Running in MIGRATE-USC mode - migrating only missing documents\n", "info")
                self._emit("progress_update", 10, "Checking synchronization...")
                
                try:
                    result = loop.run_until_complete(
                        self.migration_ops.migrate_with_checks(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            reverse=reverse,
                            progress_callback=progress_callback,
                            status_callback=status_callback,
                            cancellation_flag=lambda: self._should_cancel
                        )
                    )
                except asyncio.CancelledError:
                    self._emit("log_output", "\n❌ Migration cancelled\n", "warning")
                    return
                
                # Update final status for all collections
                for coll in result.get('successful_collections', []):
                    self._emit("collection_status", coll['id'], "Completed",
                              missing=0, migrated=coll.get('documents', 0),
                              total=coll.get('documents', 0), current_batch=0,
                              state="✅ Completed")
                
                for coll_id in result.get('failed_collections', []):
                    self._emit("collection_status", coll_id, "Failed",
                              missing=0, migrated=0, total=0, current_batch=0,
                              state="❌ Failed")
                
                self._emit("log_output", f"\n✅ Selective migration completed!\n", "success")
                self._emit("log_output", f"Total documents migrated: {result['total_documents']}\n", "info")
                self._emit("log_output", f"Already synchronized: {result.get('already_synced', 0)} collections\n", "info")
                self._emit("log_output", f"Successful collections: {len(result['successful_collections'])}\n", "success")
                if result['failed_collections']:
                    self._emit("log_output", f"Failed collections: {result['failed_collections']}\n", "error")
                
            elif mode == "check":
                if self._should_cancel:
                    self._emit("log_output", "❌ Migration cancelled by user\n", "warning")
                    return
                
                self._emit("log_output", "🔍 Running in CHECK mode - verifying synchronization\n", "info")
                self._emit("progress_update", 10, "Checking synchronization...")
                
                try:
                    result = loop.run_until_complete(
                        self.migration_ops.check_sync(
                            source_config=source_config,
                            target_config=target_config,
                            mysql_config=mysql_config,
                            check_count=True,
                            cancellation_flag=lambda: self._should_cancel
                        )
                    )
                except asyncio.CancelledError:
                    self._emit("log_output", "\n❌ Migration cancelled\n", "warning")
                    return
                
                self._emit("log_output", f"\n📊 Synchronization Check Summary\n", "header")
                self._emit("log_output", f"Total collections: {result['total_collections']}\n", "info")
                self._emit("log_output", f"Synchronized collections: {len(result['synced_collections'])}\n", "success")
                if result['collections_with_missing_points']:
                    self._emit("log_output", f"Collections with missing points: {len(result['collections_with_missing_points'])}\n", "warning")
                    self._emit("log_output", f"Total missing points: {result['total_missing_points']}\n", "warning")
                    for item in result['collections_with_missing_points']:
                        self._emit("log_output", 
                                  f"  - {item['collection_id']}: {item['missing_points']} missing "
                                  f"(source: {item['source_count']}, target: {item['target_count']})\n", 
                                  "warning")
                if result['missing_collections']:
                    self._emit("log_output", f"Collections with errors: {result['missing_collections']}\n", "error")
            
            self._emit("progress_update", 100, "Migration completed!")
            self._emit("log_output", "\n" + "=" * 80 + "\n", "header")
            self._emit("log_output", "✨ Operation completed successfully\n", "success")
            self._emit("log_output", "=" * 80 + "\n", "header")
            self._emit("status_update", "Migration completed successfully")
            
        except asyncio.CancelledError:
            self._emit("log_output", "\n❌ Migration cancelled by user\n", "warning")
            self._emit("status_update", "Migration cancelled")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.exception("Migration error")
            self._emit("log_output", f"\n❌ Error: {error_msg}\n", "error")
            self._emit("status_update", f"Error: {error_msg}")
            self._emit("error", error_msg)
        finally:
            self._is_running = False
            self._should_cancel = False
            self._migration_task = None
            self._migration_loop = None
            self._migration_process = None
            self._migration_thread = None
            self._queue = None
            self._queue_thread = None

