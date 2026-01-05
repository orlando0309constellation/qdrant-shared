"""
Migration Service - Core business logic for Qdrant collection migration.
Extracted and adapted from migrate_qdrant.py to integrate with existing architecture.
"""

import asyncio
import os
import logging
import uuid
import traceback
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime, UTC

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client import models

from qdrant_distributed.constant import SHARED_COLLECTION_NAME

# Try to import tiktoken for token counting, fallback to simple approximation
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False


logger = logging.getLogger(__name__)

# Custom log handler that can forward logs to UI
_log_callbacks = []


def add_log_callback(callback: Callable[[str, str], None]):
    """Add a callback to receive log messages for UI display."""
    _log_callbacks.append(callback)


def _log_with_callbacks(level: str, message: str, *args, **kwargs):
    """Log message and forward to callbacks with timestamp."""
    # Format message with args if provided
    if args:
        formatted_msg = message % args if '%' in message else f"{message} {args}"
    else:
        formatted_msg = message
    
    # Get current timestamp in ISO format
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds
    
    # Format log message with timestamp and level
    # Format: [YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] message
    log_entry = f"[{timestamp}] [{level.upper()}] {formatted_msg}"
    
    # Log to standard logger (without timestamp, as logger adds its own)
    getattr(logger, level.lower())(formatted_msg, **kwargs)
    
    # Forward to callbacks with timestamp
    for callback in _log_callbacks:
        try:
            callback(log_entry, level)
        except Exception:
            pass  # Ignore callback errors

# Configuration constants for batch processing
DEFAULT_BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", "1000"))
MAX_BATCH_SIZE = 10000
MIN_BATCH_SIZE = 100
DEFAULT_MAX_RETRIES = int(os.getenv("QDRANT_MAX_RETRIES", "3"))
DEFAULT_RETRY_DELAY = int(os.getenv("QDRANT_RETRY_DELAY", "2"))


def get_token_length(text: str, encoding: str = "cl100k_base") -> int:
    """
    Get token length for text using tiktoken or simple approximation.
    
    Args:
        text: Text to count tokens for
        encoding: Encoding name (default: cl100k_base)
    
    Returns:
        Token count
    """
    if _TIKTOKEN_AVAILABLE:
        try:
            enc = tiktoken.get_encoding(encoding)
            return len(enc.encode(text))
        except Exception:
            # Fallback to approximation
            pass
    
    # Simple approximation: ~4 characters per token
    return len(text) // 4


def get_batch_size() -> int:
    """Get validated batch size from environment or default"""
    batch_size = DEFAULT_BATCH_SIZE
    if batch_size > MAX_BATCH_SIZE:
        logger.warning(f"Batch size {batch_size} exceeds maximum {MAX_BATCH_SIZE}, using {MAX_BATCH_SIZE}")
        batch_size = MAX_BATCH_SIZE
    elif batch_size < MIN_BATCH_SIZE:
        logger.warning(f"Batch size {batch_size} below minimum {MIN_BATCH_SIZE}, using {MIN_BATCH_SIZE}")
        batch_size = MIN_BATCH_SIZE
    return batch_size


async def retry_operation(operation, *args, max_retries: int = DEFAULT_MAX_RETRIES, 
                          delay: int = DEFAULT_RETRY_DELAY, operation_name: str = "operation", **kwargs):
    """Generic retry mechanism for both sync and async operations"""
    _log_with_callbacks("info", f"Starting {operation_name} (max retries: {max_retries})")
    
    for attempt in range(max_retries):
        try:
            _log_with_callbacks("debug", f"{operation_name} - Attempt {attempt + 1}/{max_retries}")
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            _log_with_callbacks("info", f"{operation_name} - Attempt {attempt + 1} succeeded")
            return result
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            _log_with_callbacks("warning", f"{operation_name} - Attempt {attempt + 1}/{max_retries} failed: {error_type}: {error_msg}")
            
            # Log full traceback for debugging
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            _log_with_callbacks("debug", f"{operation_name} - Full traceback:\n{tb_str}")
            
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                _log_with_callbacks("info", f"{operation_name} - Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                _log_with_callbacks("error", f"{operation_name} - All {max_retries} attempts failed. Last error: {error_type}: {error_msg}")
                _log_with_callbacks("error", f"{operation_name} - Final traceback:\n{tb_str}")
                raise


class MultiQdrantManager:
    """Manager for multiple Qdrant instances"""
    
    def __init__(self, https: bool = False):
        self.clients: Dict[str, QdrantClient] = {}
        self.async_clients: Dict[str, AsyncQdrantClient] = {}
        self.https = https
        
    def add_client(self, name: str, url: str, port: int, api_key: Optional[str] = None, 
                   timeout: int = 3600, https: bool = None) -> QdrantClient:
        """Add a new sync Qdrant client"""
        try:
            https_val = https if https is not None else self.https
            scheme = "https" if https_val else "http"
            api_key_display = "***" if api_key else "None"
            full_url = f"{scheme}://{url}:{port}"
            
            _log_with_callbacks("info", f"Adding sync Qdrant client '{name}': {full_url} (API key: {api_key_display}, timeout: {timeout}s)")
            
            client = QdrantClient(
                url=url,
                port=port,
                api_key=api_key,
                timeout=timeout,
                https=https_val
            )
            self.clients[name] = client
            # Store connection info for later error reporting
            client._connection_info = {"name": name, "url": full_url, "host": url, "port": port}
            _log_with_callbacks("info", f"Successfully added sync Qdrant client '{name}' at {full_url}")
            return client
        except Exception as e:
            error_msg = f"Failed to add sync Qdrant client '{name}' to {scheme}://{url}:{port}: {type(e).__name__}: {str(e)}"
            _log_with_callbacks("error", error_msg)
            _log_with_callbacks("error", f"Traceback:\n{''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            raise
    
    def add_async_client(self, name: str, url: str, port: int, api_key: Optional[str] = None,
                        timeout: int = 3600, https: bool = None) -> AsyncQdrantClient:
        """Add a new async Qdrant client"""
        try:
            https_val = https if https is not None else self.https
            scheme = "https" if https_val else "http"
            api_key_display = "***" if api_key else "None"
            full_url = f"{scheme}://{url}:{port}"
            
            _log_with_callbacks("info", f"Adding async Qdrant client '{name}': {full_url} (API key: {api_key_display}, timeout: {timeout}s)")
            
            client = AsyncQdrantClient(
                url=url,
                port=port,
                api_key=api_key,
                timeout=timeout,
                https=https_val
            )
            self.async_clients[name] = client
            # Store connection info for later error reporting
            client._connection_info = {"name": name, "url": full_url, "host": url, "port": port}
            _log_with_callbacks("info", f"Successfully added async Qdrant client '{name}' at {full_url}")
            return client
        except Exception as e:
            error_msg = f"Failed to add async Qdrant client '{name}' to {scheme}://{url}:{port}: {type(e).__name__}: {str(e)}"
            _log_with_callbacks("error", error_msg)
            _log_with_callbacks("error", f"Traceback:\n{''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
            raise
    
    def get_client(self, name: str) -> QdrantClient:
        """Get a specific sync Qdrant client by name"""
        if name not in self.clients:
            error_msg = f"Sync client '{name}' not found. Available sync clients: {list(self.clients.keys())}"
            logger.error(error_msg)
            raise KeyError(error_msg)
        return self.clients[name]
    
    def get_async_client(self, name: str) -> AsyncQdrantClient:
        """Get a specific async Qdrant client by name"""
        if name not in self.async_clients:
            error_msg = f"Async client '{name}' not found. Available async clients: {list(self.async_clients.keys())}"
            logger.error(error_msg)
            raise KeyError(error_msg)
        return self.async_clients[name]
    
    def close_all(self):
        """Close all clients"""
        for name, client in self.clients.items():
            try:
                client.close()
                logger.info(f"Closed sync client: {name}")
            except Exception as e:
                logger.warning(f"Error closing sync client {name}: {e}")
        self.clients.clear()
        
        for name, client in self.async_clients.items():
            logger.info(f"Marked async client for closure: {name}")
    
    async def close_async_clients(self):
        """Close all async clients properly"""
        for name, client in self.async_clients.items():
            try:
                await client.close()
                logger.info(f"Closed async client: {name}")
            except Exception as e:
                logger.warning(f"Error closing async client {name}: {e}")
        self.async_clients.clear()


async def initialize_collection(async_client: AsyncQdrantClient, collection_name: str = None):
    """
    Initialize a single collection with both dense and sparse vectors.
    
    Args:
        async_client: Async Qdrant client
        collection_name: Name of the collection (defaults to SHARED_COLLECTION_NAME)
    """
    if collection_name is None:
        collection_name = SHARED_COLLECTION_NAME
    
    if not await async_client.collection_exists(collection_name=collection_name):
        _log_with_callbacks("info", f"📦 Collection '{collection_name}' does not exist. Creating with full configuration...")
        
        await async_client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=1536,  # OpenAI embedding size
                    distance=models.Distance.COSINE,
                    on_disk=True,
                ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=True,
                    )
                )
            },
            hnsw_config=models.HnswConfigDiff(
                payload_m=16,
                m=0,
            ),
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                ),
            ),
            on_disk_payload=True,
            shard_number=12,  # 12 shards for future node expansion
            replication_factor=2,  # 2x replication for fault tolerance
        )
        
        _log_with_callbacks("info", f"✅ Created collection '{collection_name}' with dense and sparse vectors")
        
        # Create payload indexes
        try:
            await async_client.create_payload_index(
                collection_name=collection_name,
                field_name="collection_id",
                field_schema=models.PayloadSchemaType.UUID,
            )
            _log_with_callbacks("info", f"✅ Created payload index for 'collection_id'")
        except Exception as e:
            _log_with_callbacks("warning", f"⚠️ Could not create payload index for 'collection_id' with PayloadSchemaType: {e}")
            # Try with UuidIndexParams as shown in the original code
            try:
                await async_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="collection_id",
                    field_schema=models.UuidIndexParams(
                        type=models.UuidIndexType.UUID,
                    ),
                )
                _log_with_callbacks("info", f"✅ Created payload index for 'collection_id' (using UuidIndexParams)")
            except Exception as e2:
                _log_with_callbacks("warning", f"⚠️ Could not create payload index for 'collection_id': {e2}")
        
        try:
            await async_client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.source",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            _log_with_callbacks("info", f"✅ Created payload index for 'metadata.source'")
        except Exception as e:
            _log_with_callbacks("warning", f"⚠️ Could not create payload index for 'metadata.source' with PayloadSchemaType: {e}")
            # Try with KeywordIndexParams as shown in the original code
            try:
                await async_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.source",
                    field_schema=models.KeywordIndexParams(
                        type=models.KeywordIndexType.KEYWORD,
                    ),
                )
                _log_with_callbacks("info", f"✅ Created payload index for 'metadata.source' (using KeywordIndexParams)")
            except Exception as e2:
                _log_with_callbacks("warning", f"⚠️ Could not create payload index for 'metadata.source': {e2}")
        
        # Wait a moment for collection to be fully available
        await asyncio.sleep(1)
        _log_with_callbacks("info", f"✅ Collection '{collection_name}' initialization complete")
    else:
        _log_with_callbacks("info", f"✅ Collection '{collection_name}' already exists")


async def ensure_collection_exists(
    target_client: AsyncQdrantClient, 
    collection_name: str,
    source_client: Optional[AsyncQdrantClient] = None
):
    """
    Ensure target collection exists, create if it doesn't.
    Uses initialize_collection for proper configuration.
    
    Args:
        target_client: Target Qdrant async client where collection should exist
        collection_name: Name of the collection to ensure exists
        source_client: Optional source client (not used, kept for compatibility)
    """
    try:
        collection_info = await target_client.get_collection(collection_name)
        _log_with_callbacks("info", f"✅ Collection '{collection_name}' already exists")
        return collection_info
    except Exception as e:
        # Collection doesn't exist - initialize it with proper configuration
        _log_with_callbacks("info", f"📦 Collection '{collection_name}' does not exist. Initializing...")
        await initialize_collection(target_client, collection_name)
        
        # Verify it was created
        try:
            created_info = await target_client.get_collection(collection_name)
            return created_info
        except Exception as verify_error:
            error_type = type(verify_error).__name__
            error_str = str(verify_error)
            _log_with_callbacks("error", f"❌ Failed to verify collection '{collection_name}' after creation: {error_type}: {error_str}")
            raise


async def get_collections_from_mysql():
    """
    Get collections from MySQL database.
    Returns list of collection objects with 'id' and 'collection_name' attributes.
    """
    from qdrant_distributed.config import MySQLManager
    
    _log_with_callbacks("info", "Fetching collections from MySQL database...")
    
    if MySQLManager.connection is None:
        error_msg = "MySQL connection not available. Initialize MySQL first."
        _log_with_callbacks("error", error_msg)
        raise ValueError(error_msg)
    
    cursor = MySQLManager.connection.cursor(dictionary=True)
    try:
        # Query collections table - try common table/column name variations
        query_attempts = [
            "SELECT id, collection_name FROM collections",
            "SELECT id, name FROM collections",
            "SELECT collection_id as id, collection_name FROM collections"
        ]
        
        rows = None
        for query in query_attempts:
            try:
                _log_with_callbacks("debug", f"Trying MySQL query: {query}")
                cursor.execute(query)
                rows = cursor.fetchall()
                _log_with_callbacks("info", f"Successfully executed query: {query}")
                break
            except Exception as e:
                _log_with_callbacks("debug", f"Query failed: {query} - {type(e).__name__}: {str(e)}")
                continue
        
        if rows is None:
            error_msg = "Failed to query collections table with any known schema"
            _log_with_callbacks("error", error_msg)
            raise ValueError(error_msg)
        
        _log_with_callbacks("info", f"Retrieved {len(rows)} collection records from MySQL")
        
        # Create simple objects with id and collection_name
        collections = []
        for row in rows:
            class Collection:
                def __init__(self, id, collection_name):
                    self.id = id
                    self.collection_name = collection_name or str(id)
            # Handle different column name possibilities
            coll_id = row.get('id') or row.get('collection_id')
            coll_name = row.get('collection_name') or row.get('name') or str(coll_id)
            collections.append(Collection(coll_id, coll_name))
            _log_with_callbacks("debug", f"  - Collection: id={coll_id}, name={coll_name}")
        
        _log_with_callbacks("info", f"Successfully retrieved {len(collections)} collections from database")
        return collections
    except Exception as e:
        error_msg = f"Error fetching collections from database: {type(e).__name__}: {str(e)}"
        _log_with_callbacks("error", error_msg)
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        _log_with_callbacks("error", f"Traceback:\n{tb_str}")
        raise
    finally:
        cursor.close()


async def general_summary(collection_id: str, documents: List[Any], 
                          embedding_callback: Optional[Callable] = None):
    """
    Create general summaries for each source group and save them as new points.
    
    Args:
        collection_id: The collection ID to process
        documents: List of documents from the collection
        embedding_callback: Optional async function to generate embeddings
    
    Returns:
        List of summary point structures
    """
    try:
        logger.info(f"Creating general summaries for collection: {collection_id}")
        
        # Group documents by metadata.source
        source_groups = {}
        for doc in documents:
            source = doc.payload.get('metadata', {}).get('source', 'unknown')
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(doc)
        
        logger.info(f"Found {len(source_groups)} source groups")
        
        # Create summary for each source group
        summary_points = []
        for source, source_docs in source_groups.items():
            logger.info(f"Processing source: {source} with {len(source_docs)} documents")
            
            # Combine all page_content from this source
            combined_content = "\n\n".join([doc.payload.get('summary', '') for doc in source_docs])
            
            # Calculate total tokens for this source
            total_tokens = get_token_length(combined_content, "cl100k_base")
            
            # Generate embedding if callback provided, otherwise use empty vector
            if embedding_callback:
                try:
                    dense_vector = await embedding_callback(combined_content)
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for source {source}: {e}")
                    # Use zero vector as fallback (dimension will depend on your model)
                    dense_vector = []
            else:
                # No embedding callback - skip summary creation or use placeholder
                logger.warning(f"No embedding callback provided, skipping summary for source {source}")
                continue
            
            # Create summary point for this source
            summary_point = models.PointStruct(
                id=f"{uuid.uuid4()}",
                vector={
                    "dense": dense_vector,
                    "sparse": models.SparseVector(indices=[], values=[])
                },
                payload={
                    "page_content": combined_content,
                    "metadata": {
                        "type": "general_summary",
                        "source": source,
                        "tokens": total_tokens,
                        "points_number": len(source_docs)
                    },
                    "c_id": collection_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            
            summary_points.append(summary_point)
            logger.info(f"Created summary for {source}: {len(source_docs)} docs, {total_tokens} tokens")
        
        return summary_points
        
    except Exception as e:
        logger.exception(f"Error creating general summaries for collection {collection_id}: {e}")
        raise


async def save_summaries(qdrant_manager: MultiQdrantManager, collection_id: str, 
                        summary_points: List[models.PointStruct]):
    """
    Save general summary points to the target instance.
    
    Args:
        qdrant_manager: The Qdrant manager instance
        collection_id: The collection ID
        summary_points: List of summary points to save
    """
    try:
        if not summary_points:
            logger.info(f"No summary points to save for collection {collection_id}")
            return
        
        logger.info(f"Checking existing summaries for collection {collection_id}")
        
        # Get the target client (distributed)
        target_client = qdrant_manager.get_client('distributed')
        
        # Load all existing summaries for this collection
        existing_summaries = {}
        offset = None
        
        while True:
            try:
                search_result = target_client.scroll(
                    collection_name=SHARED_COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="c_id",
                                match=models.MatchValue(value=collection_id)
                            ),
                            models.FieldCondition(
                                key="metadata.type",
                                match=models.MatchValue(value="general_summary")
                            )
                        ]
                    ),
                    with_payload=True,
                    with_vectors=False,
                    limit=1000,
                    offset=offset
                )
                
                documents = search_result[0]
                next_page_offset = search_result[1]
                
                if not documents:
                    break
                
                for doc in documents:
                    source = doc.payload.get('metadata', {}).get('source', 'unknown')
                    page_content = doc.payload.get('page_content', '')
                    if source and page_content:
                        existing_summaries[source] = page_content
                
                if next_page_offset is None:
                    break
                offset = next_page_offset
                
            except Exception as e:
                logger.warning(f"Error loading existing summaries: {e}")
                break
        
        logger.info(f"Found {len(existing_summaries)} existing summaries")
        
        # Filter out summaries that already exist with same content
        new_summary_points = []
        for point in summary_points:
            source = point.payload.get('metadata', {}).get('source', 'unknown')
            page_content = point.payload.get('page_content', '')
            
            if source in existing_summaries and existing_summaries[source] == page_content:
                logger.info(f"Summary for source {source} already exists with same content, skipping")
            else:
                new_summary_points.append(point)
        
        if not new_summary_points:
            logger.info(f"All summaries for collection {collection_id} already exist")
            return
        
        logger.info(f"Saving {len(new_summary_points)} new summary points")
        
        # Save new summary points
        await retry_operation(
            target_client.upsert,
            collection_name=SHARED_COLLECTION_NAME,
            points=new_summary_points,
            max_retries=3
        )
        
        logger.info(f"Successfully saved {len(new_summary_points)} summary points for collection {collection_id}")
        
    except Exception as e:
        logger.exception(f"Error saving summaries for collection {collection_id}: {e}")
        raise


async def process_collection(collection_id: str, qdrant_manager: MultiQdrantManager,
                            progress_callback: Optional[Callable] = None,
                            embedding_callback: Optional[Callable] = None,
                            status_callback: Optional[Callable] = None,
                            cancellation_flag: Optional[Callable[[], bool]] = None):
    """
    Process a collection by migrating from source to target Qdrant instance.
    
    Args:
        collection_id: Collection ID to migrate
        qdrant_manager: MultiQdrantManager instance
        progress_callback: Optional callback for progress updates (collection_id, current, total)
        embedding_callback: Optional callback for generating embeddings
        status_callback: Optional callback for status updates
        cancellation_flag: Optional callable that returns True if migration should be cancelled
    
    Returns:
        List of all migrated documents
    """
    start_time = datetime.now(UTC)
    try:
        _log_with_callbacks("info", f"🔄 Processing collection: {collection_id}")
        
        # Notify status callback
        if status_callback:
            try:
                status_callback(collection_id, "Starting", missing=0, migrated=0, total=0, current_batch=0, state="Initializing...")
            except Exception:
                pass
        
        source_client = qdrant_manager.get_client('default')
        target_client = qdrant_manager.get_client('distributed')
        source_async = qdrant_manager.get_async_client('default_async')
        target_async = qdrant_manager.get_async_client('distributed_async')
        
        # Ensure target collection exists before processing
        try:
            await ensure_collection_exists(target_async, SHARED_COLLECTION_NAME, source_client=source_async)
        except Exception as e:
            _log_with_callbacks("warning", f"⚠️ Could not ensure collection exists: {e}. Continuing anyway...")
        
        batch_size = get_batch_size()
        _log_with_callbacks("info", f"  Configuration: batch_size={batch_size}, collection_name={SHARED_COLLECTION_NAME}")
        
        offset = None
        all_documents = []
        total_documents = 0
        batch_number = 0
        total_batches = 0  # Initialize total_batches to track estimated total batches
        
        while True:
            # Check for cancellation
            if cancellation_flag and cancellation_flag():
                _log_with_callbacks("warning", f"Migration cancelled. Stopping collection {collection_id} processing.")
                break
            
            batch_number += 1
            _log_with_callbacks("debug", f"  Batch {batch_number}: Fetching documents for collection {collection_id}, offset: {offset}")
            
            try:
                # Fetch documents in batches
                _log_with_callbacks("debug", f"  Batch {batch_number}: Executing scroll query on source...")
                search_result = source_client.scroll(
                    collection_name=SHARED_COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    ),
                    with_payload=True,
                    with_vectors=True,
                    limit=batch_size,
                    offset=offset
                )
                
                documents = search_result[0]
                next_page_offset = search_result[1]
                
                _log_with_callbacks("debug", f"  Batch {batch_number}: Scroll query completed, retrieved {len(documents) if documents else 0} documents")
                
                if not documents:
                    _log_with_callbacks("info", f"  No more documents for collection {collection_id}")
                    break
                
                all_documents.extend(documents)
                total_documents += len(documents)
                _log_with_callbacks("info", f"  Batch {batch_number}: Fetched {len(documents)} documents (total: {total_documents}) for collection_id: {collection_id}")
                
                # Prepare points for the target instance
                _log_with_callbacks("debug", f"  Batch {batch_number}: Preparing {len(documents)} points for migration...")
                points = []
                points_number = len(documents)
                for idx, doc in enumerate(documents):
                    point = models.PointStruct(
                        id=doc.id,
                        vector=doc.vector,
                        payload=doc.payload
                    )
                    if "metadata" not in point.payload:
                        point.payload["metadata"] = {}
                    point.payload["metadata"]["points_number"] = points_number
                    page_content = doc.payload.get("page_content", "")
                    point.payload["metadata"]["tokens"] = get_token_length(page_content, "cl100k_base")
                    points.append(point)
                    
                    if (idx + 1) % 100 == 0:
                        _log_with_callbacks("debug", f"  Batch {batch_number}: Prepared {idx + 1}/{len(documents)} points...")
                
                _log_with_callbacks("debug", f"  Batch {batch_number}: Prepared {len(points)} points, sending to target instance...")
                
                # Send documents to the target instance with retry
                try:
                    await retry_operation(
                        target_client.upsert,
                        collection_name=SHARED_COLLECTION_NAME,
                        points=points,
                        max_retries=3,
                        operation_name=f"Upsert batch {batch_number} for collection {collection_id}"
                    )
                    _log_with_callbacks("info", f"  Batch {batch_number}: ✅ Successfully sent {len(points)} documents to target instance")
                except Exception as e:
                    error_msg = f"Failed to upsert batch {batch_number} after retries: {type(e).__name__}: {str(e)}"
                    _log_with_callbacks("error", error_msg)
                    tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                    raise
                
                # Update progress if callback provided
                if progress_callback:
                    try:
                        progress_callback(collection_id, total_documents, None)
                    except Exception as e:
                        _log_with_callbacks("warning", f"Progress callback error: {e}")
                
                # Update total batches estimate (if we have enough info)
                # We can't know exact total until we finish, but we can estimate
                if total_batches == 0 and next_page_offset is None:
                    # Last batch, we now know the total
                    total_batches = batch_number
                elif total_batches == 0 and batch_number > 0:
                    # Estimate: at least current batch, possibly more
                    total_batches = batch_number + 1
                
                # Update status callback
                if status_callback:
                    try:
                        status_callback(collection_id, "Processing", missing=0, migrated=total_documents,
                                      total=0, current_batch=batch_number, state=f"Batch {batch_number}: {len(points)} documents",
                                      total_batches=total_batches)
                    except Exception:
                        pass
                
                # Update offset for next batch
                if next_page_offset is None:
                    _log_with_callbacks("debug", f"  Reached end of collection {collection_id}")
                    break
                offset = next_page_offset
                
            except Exception as e:
                error_msg = f"Error in batch {batch_number} for collection {collection_id}: {type(e).__name__}: {str(e)}"
                _log_with_callbacks("error", error_msg)
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                raise
        
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        _log_with_callbacks("info", f"  ✅ Completed fetching {total_documents} documents in {batch_number} batches (took {elapsed:.2f}s)")
        
        # Create general summaries if embedding callback provided
        if embedding_callback:
            _log_with_callbacks("info", f"  Creating general summaries for collection {collection_id}...")
            try:
                summary_points = await general_summary(collection_id, all_documents, embedding_callback)
                
                if summary_points:
                    await save_summaries(qdrant_manager, collection_id, summary_points)
                    _log_with_callbacks("info", f"  ✅ Created and saved {len(summary_points)} summary points")
            except Exception as e:
                _log_with_callbacks("warning", f"  Failed to create summaries: {type(e).__name__}: {str(e)}")
                # Don't fail the whole migration if summaries fail
        
        total_elapsed = (datetime.now(UTC) - start_time).total_seconds()
        _log_with_callbacks("info", f"✅ Successfully processed collection {collection_id}: {total_documents} documents migrated in {total_elapsed:.2f}s")
        
        # Finalize total batches
        if total_batches == 0:
            total_batches = batch_number if batch_number > 0 else 1
        
        # Notify completion
        if status_callback:
            try:
                status_callback(collection_id, "Completed", missing=0, migrated=total_documents,
                              total=total_documents, current_batch=batch_number, state="✅ Completed",
                              total_batches=total_batches)
            except Exception:
                pass
        
        return all_documents
        
    except Exception as e:
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        error_msg = f"❌ Error processing collection {collection_id} (after {elapsed:.2f}s): {type(e).__name__}: {str(e)}"
        _log_with_callbacks("error", error_msg)
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        _log_with_callbacks("error", f"Full traceback:\n{tb_str}")
        
        # Notify failure
        if status_callback:
            try:
                final_total_batches = total_batches if total_batches > 0 else batch_number
                status_callback(collection_id, "Failed", missing=0, migrated=total_documents,
                              total=0, current_batch=batch_number, state=f"❌ Failed: {str(e)[:50]}",
                              total_batches=final_total_batches)
            except Exception:
                pass
        
        raise


async def process_collection_missing_only(collection_id: str, qdrant_manager: MultiQdrantManager,
                                         progress_callback: Optional[Callable] = None,
                                         embedding_callback: Optional[Callable] = None,
                                         status_callback: Optional[Callable] = None,
                                         cancellation_flag: Optional[Callable[[], bool]] = None,
                                         expected_missing_count: Optional[int] = None):
    """
    Process only missing documents for a collection.
    
    Args:
        collection_id: Collection ID to process
        qdrant_manager: MultiQdrantManager instance
        progress_callback: Optional callback for progress updates
        embedding_callback: Optional callback for generating embeddings
    
    Returns:
        List of migrated documents
    """
    start_time = datetime.now(UTC)
    try:
        _log_with_callbacks("info", f"🔄 Processing missing documents for collection: {collection_id}")
        
        # Notify status callback
        if status_callback:
            try:
                status_callback(collection_id, "Starting", missing=0, migrated=0, total=0, current_batch=0, state="Initializing...")
            except Exception:
                pass
        
        source_client = qdrant_manager.get_client('default')
        target_client = qdrant_manager.get_client('distributed')
        source_async = qdrant_manager.get_async_client('default_async')
        target_async = qdrant_manager.get_async_client('distributed_async')
        
        # Ensure target collection exists before processing
        try:
            await ensure_collection_exists(target_async, SHARED_COLLECTION_NAME, source_client=source_async)
        except Exception as e:
            _log_with_callbacks("warning", f"⚠️ Could not ensure collection exists: {e}. Continuing anyway...")
        
        batch_size = get_batch_size()
        _log_with_callbacks("info", f"  Configuration: batch_size={batch_size}, collection_name={SHARED_COLLECTION_NAME}")
        
        # Fetch existing document IDs from target
        _log_with_callbacks("info", f"  Step 1: Fetching existing document IDs from target instance...")
        existing_target_ids = set()
        offset = None
        existing_batch_count = 0
        
        while True:
            existing_batch_count += 1
            _log_with_callbacks("debug", f"  Fetching existing documents batch {existing_batch_count}, offset: {offset}")
            try:
                target_docs_result = target_client.scroll(
                    collection_name=SHARED_COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    ),
                    with_payload=False,
                    with_vectors=False,
                    limit=batch_size,
                    offset=offset
                )
                
                target_docs = target_docs_result[0]
                next_page_offset = target_docs_result[1]
                
                if not target_docs:
                    _log_with_callbacks("debug", f"  No more existing documents in target")
                    break
                
                existing_target_ids.update(doc.id for doc in target_docs)
                _log_with_callbacks("debug", f"  Fetched {len(target_docs)} existing documents in batch {existing_batch_count} (total existing: {len(existing_target_ids)})")
                
                if next_page_offset is None:
                    break
                offset = next_page_offset
                
            except Exception as e:
                error_msg = f"Error fetching existing documents batch {existing_batch_count}: {type(e).__name__}: {str(e)}"
                _log_with_callbacks("error", error_msg)
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                break
        
        _log_with_callbacks("info", f"  ✅ Found {len(existing_target_ids)} existing documents in target instance")
        
        # Process missing documents
        _log_with_callbacks("info", f"  Step 2: Processing missing documents from source...")
        offset = None
        all_missing_documents = []
        total_documents = 0
        batch_number = 0
        
        # Calculate total batches
        batch_size = get_batch_size()
        total_batches = 0
        if expected_missing_count and expected_missing_count > 0:
            total_batches = (expected_missing_count + batch_size - 1) // batch_size  # Ceiling division
        
        # Update status: Starting migration
        if status_callback:
            try:
                status_callback(collection_id, "Processing", 
                              missing=expected_missing_count if expected_missing_count else 0, 
                              migrated=0, 
                              total=expected_missing_count if expected_missing_count else 0, 
                              current_batch=0, 
                              state="Starting migration...",
                              total_batches=total_batches)
            except Exception:
                pass
        
        while True:
            # Check for cancellation
            if cancellation_flag and cancellation_flag():
                _log_with_callbacks("warning", f"Migration cancelled. Stopping collection {collection_id} processing.")
                break
            
            batch_number += 1
            _log_with_callbacks("debug", f"  Batch {batch_number}: Fetching documents from source, offset: {offset}")
            
            try:
                search_result = source_client.scroll(
                    collection_name=SHARED_COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    ),
                    with_payload=True,
                    with_vectors=True,
                    limit=batch_size,
                    offset=offset
                )
                
                documents = search_result[0]
                next_page_offset = search_result[1]
                
                if not documents:
                    _log_with_callbacks("debug", f"  No more documents for collection {collection_id}")
                    break
                
                # Filter out documents that already exist in target
                missing_documents = [doc for doc in documents if doc.id not in existing_target_ids]
                _log_with_callbacks("debug", f"  Batch {batch_number}: Found {len(missing_documents)} missing documents out of {len(documents)} total")
                
                if missing_documents:
                    _log_with_callbacks("debug", f"  Batch {batch_number}: Preparing {len(missing_documents)} points for migration...")
                    points = []
                    points_number = len(missing_documents)
                    for doc in missing_documents:
                        point = models.PointStruct(
                            id=doc.id,
                            vector=doc.vector,
                            payload=doc.payload
                        )
                        if "metadata" not in point.payload:
                            point.payload["metadata"] = {}
                        point.payload["metadata"]["points_number"] = points_number
                        point.payload["metadata"]["tokens"] = get_token_length(doc.payload.get("page_content", ""), "cl100k_base")
                        points.append(point)
                    
                    _log_with_callbacks("debug", f"  Batch {batch_number}: Sending {len(points)} points to target...")
                    try:
                        await retry_operation(
                            target_client.upsert,
                            collection_name=SHARED_COLLECTION_NAME,
                            points=points,
                            max_retries=3,
                            operation_name=f"Upsert missing batch {batch_number} for collection {collection_id}"
                        )
                        _log_with_callbacks("info", f"  Batch {batch_number}: ✅ Successfully sent {len(points)} missing documents to target")
                    except Exception as e:
                        # Extract more detailed error message for 500 errors
                        error_type = type(e).__name__
                        error_str = str(e)
                        
                        # Try to extract the actual error message from Qdrant 500 errors
                        if "500" in error_str or "Internal Server Error" in error_str:
                            # Look for the actual error message in the response
                            if "RocksDB" in error_str:
                                error_summary = "Qdrant server database error (RocksDB IO error). The server may be experiencing storage issues."
                            elif "Service internal error" in error_str:
                                error_summary = "Qdrant server internal error. The server may be overloaded or experiencing issues."
                            else:
                                error_summary = "Qdrant server returned 500 Internal Server Error. Check server logs for details."
                            
                            error_msg = f"Failed to upsert missing documents batch {batch_number} after retries: {error_summary}"
                            _log_with_callbacks("error", error_msg)
                            _log_with_callbacks("error", f"Full error: {error_type}: {error_str[:500]}")  # Limit length
                        else:
                            error_msg = f"Failed to upsert missing documents batch {batch_number} after retries: {error_type}: {error_str}"
                            _log_with_callbacks("error", error_msg)
                        
                        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                        _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                        raise
                    
                    all_missing_documents.extend(missing_documents)
                    total_documents += len(missing_documents)
                    
                    if progress_callback:
                        try:
                            progress_callback(collection_id, total_documents, None)
                        except Exception as e:
                            _log_with_callbacks("warning", f"Progress callback error: {e}")
                    
                    # Update status callback
                    if status_callback:
                        try:
                            remaining = (expected_missing_count - total_documents) if expected_missing_count else 0
                            status_callback(collection_id, "Processing", 
                                          missing=max(0, remaining), 
                                          migrated=total_documents,
                                          total=expected_missing_count if expected_missing_count else total_documents,
                                          current_batch=batch_number, 
                                          state=f"Batch {batch_number}: Migrated {len(points)} documents ({total_documents} total)",
                                          total_batches=total_batches)
                        except Exception:
                            pass
                else:
                    _log_with_callbacks("debug", f"  Batch {batch_number}: No missing documents in this batch, skipping...")
            
            except Exception as e:
                error_msg = f"Error in batch {batch_number} for collection {collection_id}: {type(e).__name__}: {str(e)}"
                _log_with_callbacks("error", error_msg)
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                raise
            
            if next_page_offset is None:
                _log_with_callbacks("debug", f"  Reached end of collection {collection_id}")
                break
            offset = next_page_offset
        
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        _log_with_callbacks("info", f"  ✅ Completed processing {total_documents} missing documents in {batch_number} batches (took {elapsed:.2f}s)")
        
        # Create summaries if callback provided
        if embedding_callback and all_missing_documents:
            _log_with_callbacks("info", f"  Creating general summaries for collection {collection_id}...")
            try:
                summary_points = await general_summary(collection_id, all_missing_documents, embedding_callback)
                
                if summary_points:
                    await save_summaries(qdrant_manager, collection_id, summary_points)
                    _log_with_callbacks("info", f"  ✅ Created and saved {len(summary_points)} summary points")
            except Exception as e:
                _log_with_callbacks("warning", f"  Failed to create summaries: {type(e).__name__}: {str(e)}")
        
        total_elapsed = (datetime.now(UTC) - start_time).total_seconds()
        _log_with_callbacks("info", f"✅ Successfully processed collection {collection_id}: {total_documents} missing documents migrated in {total_elapsed:.2f}s")
        
        # Notify completion
        if status_callback:
            try:
                status_callback(collection_id, "Completed", missing=0, migrated=total_documents,
                              total=total_documents, current_batch=batch_number, state="✅ Completed")
            except Exception:
                pass
        
        return all_missing_documents
        
    except Exception as e:
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        error_msg = f"❌ Error processing missing documents for collection {collection_id} (after {elapsed:.2f}s): {type(e).__name__}: {str(e)}"
        _log_with_callbacks("error", error_msg)
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        _log_with_callbacks("error", f"Full traceback:\n{tb_str}")
        
        # Notify failure
        if status_callback:
            try:
                status_callback(collection_id, "Failed", missing=0, migrated=total_documents,
                              total=0, current_batch=batch_number, state=f"❌ Failed: {str(e)[:50]}")
            except Exception:
                pass
        
        raise


async def migrate_all(qdrant_manager: MultiQdrantManager,
                     progress_callback: Optional[Callable] = None,
                     embedding_callback: Optional[Callable] = None,
                     status_callback: Optional[Callable] = None,
                     cancellation_flag: Optional[Callable[[], bool]] = None):
    """
    Migrate all collections without checking what's already in target.
    
    Args:
        qdrant_manager: MultiQdrantManager instance
        progress_callback: Optional callback for progress updates
        embedding_callback: Optional callback for generating embeddings
    
    Returns:
        Dictionary with migration results
    """
    collections = await get_collections_from_mysql()
    logger.info(f"Found {len(collections)} collections to migrate")
    
    total_documents_migrated = 0
    failed_collections = []
    successful_collections = []
    
    for i, collection in enumerate(collections, 1):
        # Check for cancellation
        if cancellation_flag and cancellation_flag():
            _log_with_callbacks("warning", f"Migration cancelled. Processed {i-1}/{len(collections)} collections.")
            break
        
        logger.info(f"Processing collection {i}/{len(collections)}: {collection.id}")
        try:
            documents = await retry_operation(
                process_collection,
                collection.id,
                qdrant_manager,
                progress_callback,
                embedding_callback,
                status_callback,
                cancellation_flag,
                max_retries=DEFAULT_MAX_RETRIES
            )
            if documents:
                total_documents_migrated += len(documents)
                successful_collections.append({
                    'id': collection.id,
                    'name': collection.collection_name,
                    'documents': len(documents)
                })
                logger.info(f"Collection {collection.id} migrated: {len(documents)} documents")
            else:
                logger.warning(f"Collection {collection.id}: No documents found")
        except Exception as e:
            logger.exception(f"Collection {collection.id} failed after all retries: {e}")
            failed_collections.append(collection.id)
    
    return {
        'total_documents': total_documents_migrated,
        'successful_collections': successful_collections,
        'failed_collections': failed_collections,
        'total_collections': len(collections)
    }


async def migrate_with_checks(qdrant_manager: MultiQdrantManager,
                             progress_callback: Optional[Callable] = None,
                             embedding_callback: Optional[Callable] = None,
                             status_callback: Optional[Callable] = None,
                             cancellation_flag: Optional[Callable[[], bool]] = None):
    """
    Migrate only missing documents after checking what's already in target.
    
    Args:
        qdrant_manager: MultiQdrantManager instance
        progress_callback: Optional callback for progress updates
        embedding_callback: Optional callback for generating embeddings
    
    Returns:
        Dictionary with migration results
    """
    _log_with_callbacks("info", "🔍 Starting migration with necessary checks...")
    
    collections = await get_collections_from_mysql()
    _log_with_callbacks("info", f"Found {len(collections)} collections in database")
    
    source_client = qdrant_manager.get_client('default')
    target_client = qdrant_manager.get_client('distributed')
    
    collections_to_migrate = []
    collections_already_synced = []
    
    # Check each collection
    _log_with_callbacks("info", "Checking synchronization status for each collection...")
    for i, collection in enumerate(collections, 1):
        collection_id = collection.id
        _log_with_callbacks("info", f"Checking collection {i}/{len(collections)}: {collection_id}")
        
        try:
            # Get count from source
            _log_with_callbacks("debug", f"  Collection {collection_id}: Counting documents in source...")
            
            # Update status: Checking
            if status_callback:
                try:
                    status_callback(collection_id, "Checking", missing=0, migrated=0, total=0, current_batch=0, state="Checking synchronization...")
                except Exception:
                    pass
            
            try:
                # Log connection details for debugging
                connection_info = getattr(source_client, '_connection_info', None)
                if connection_info:
                    _log_with_callbacks("debug", f"  Collection {collection_id}: Connecting to source Qdrant '{connection_info['name']}' at {connection_info['url']}")
                else:
                    try:
                        source_url = getattr(source_client, '_client', None)
                        if source_url:
                            url_info = getattr(source_url, 'url', 'unknown')
                            _log_with_callbacks("debug", f"  Collection {collection_id}: Connecting to source at {url_info}")
                    except Exception:
                        pass
                
                source_count_result = source_client.count(
                    collection_name=SHARED_COLLECTION_NAME,
                    count_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    )
                )
                source_count = source_count_result.count
                _log_with_callbacks("debug", f"  Collection {collection_id}: Source count = {source_count}")
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                # Extract connection info if available
                conn_info_str = ""
                conn_info = getattr(source_client, '_connection_info', None)
                if conn_info:
                    conn_info_str = f" (source Qdrant '{conn_info['name']}' at {conn_info['url']})"
                else:
                    try:
                        source_url = getattr(source_client, '_client', None)
                        if source_url:
                            url_info = getattr(source_url, 'url', 'unknown')
                            conn_info_str = f" (trying to connect to source at: {url_info})"
                    except Exception:
                        pass
                
                error_msg_full = f"Failed to count documents in source for collection {collection_id}{conn_info_str}: {error_type}: {error_msg}"
                _log_with_callbacks("error", error_msg_full)
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                raise
            
            if source_count == 0:
                _log_with_callbacks("warning", f"  Collection {collection_id}: No documents in source, skipping")
                if status_callback:
                    try:
                        status_callback(collection_id, "Skipped", missing=0, migrated=0, total=0, current_batch=0, state="No documents in source",
                                      total_batches=0)
                    except Exception:
                        pass
                continue
            
            # Get count from target
            _log_with_callbacks("debug", f"  Collection {collection_id}: Counting documents in target...")
            try:
                # Log connection details for debugging
                connection_info = getattr(target_client, '_connection_info', None)
                if connection_info:
                    _log_with_callbacks("debug", f"  Collection {collection_id}: Connecting to target Qdrant '{connection_info['name']}' at {connection_info['url']}")
                else:
                    try:
                        target_url = getattr(target_client, '_client', None)
                        if target_url:
                            url_info = getattr(target_url, 'url', 'unknown')
                            _log_with_callbacks("debug", f"  Collection {collection_id}: Connecting to target at {url_info}")
                    except Exception:
                        pass
                
                target_count_result = target_client.count(
                    collection_name=SHARED_COLLECTION_NAME,
                    count_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    )
                )
                target_count = target_count_result.count
                _log_with_callbacks("debug", f"  Collection {collection_id}: Target count = {target_count}")
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                # Extract connection info if available
                conn_info_str = ""
                conn_info = getattr(target_client, '_connection_info', None)
                if conn_info:
                    conn_info_str = f" (target Qdrant '{conn_info['name']}' at {conn_info['url']})"
                else:
                    try:
                        target_url = getattr(target_client, '_client', None)
                        if target_url:
                            url_info = getattr(target_url, 'url', 'unknown')
                            conn_info_str = f" (trying to connect to target at: {url_info})"
                    except Exception:
                        pass
                
                error_msg_full = f"Failed to count documents in target for collection {collection_id}{conn_info_str}: {error_type}: {error_msg}"
                _log_with_callbacks("error", error_msg_full)
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                raise
            
            if source_count != target_count:
                missing_points = source_count - target_count
                collections_to_migrate.append({
                    'collection_id': collection_id,
                    'source_count': source_count,
                    'target_count': target_count,
                    'missing_points': missing_points
                })
                _log_with_callbacks("warning", f"  Collection {collection_id}: ⚠️ Needs migration - {missing_points} points missing (source: {source_count}, target: {target_count})")
                
                # Calculate total batches for this collection
                batch_size = get_batch_size()
                total_batches = (missing_points + batch_size - 1) // batch_size if missing_points > 0 else 0
                
                # Update status: Needs migration
                if status_callback:
                    try:
                        status_callback(collection_id, "Pending", missing=missing_points, migrated=target_count,
                                      total=source_count, current_batch=0, state=f"Needs migration: {missing_points} missing",
                                      total_batches=total_batches)
                    except Exception:
                        pass
            else:
                collections_already_synced.append(collection_id)
                _log_with_callbacks("info", f"  Collection {collection_id}: ✅ Already synchronized ({source_count} documents)")
                
                # Update status: Already synced
                if status_callback:
                    try:
                        status_callback(collection_id, "Synced", missing=0, migrated=source_count,
                                      total=source_count, current_batch=0, state="✅ Already synchronized",
                                      total_batches=0)
                    except Exception:
                        pass
                
        except Exception as e:
            error_msg = f"Error checking collection {collection_id}: {type(e).__name__}: {str(e)}"
            _log_with_callbacks("error", error_msg)
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            _log_with_callbacks("error", f"Traceback:\n{tb_str}")
            collections_to_migrate.append({
                'collection_id': collection_id,
                'source_count': 0,
                'target_count': 0,
                'missing_points': 0
            })
    
    _log_with_callbacks("info", f"\n📊 Check Summary:")
    _log_with_callbacks("info", f"  Collections already synchronized: {len(collections_already_synced)}")
    _log_with_callbacks("info", f"  Collections needing migration: {len(collections_to_migrate)}")
    
    if collections_already_synced:
        _log_with_callbacks("info", f"  Already synced: {', '.join(collections_already_synced[:5])}{'...' if len(collections_already_synced) > 5 else ''}")
    
    if not collections_to_migrate:
        _log_with_callbacks("info", "✅ All collections are already synchronized! No migration needed.")
        return {
            'total_documents': 0,
            'successful_collections': [],
            'failed_collections': [],
            'total_collections': len(collections),
            'already_synced': len(collections_already_synced)
        }
    
    # Migrate missing documents
    _log_with_callbacks("info", f"\n🚀 Starting selective migration of {len(collections_to_migrate)} collections...")
    total_documents_migrated = 0
    failed_collections = []
    successful_collections = []
    
    for i, migration_item in enumerate(collections_to_migrate, 1):
        collection_id = migration_item['collection_id']
        missing_points = migration_item['missing_points']
        _log_with_callbacks("info", f"\nMigrating missing documents {i}/{len(collections_to_migrate)} for collection: {collection_id} (missing {missing_points} points)")
        try:
            documents = await retry_operation(
                process_collection_missing_only,
                collection_id,
                qdrant_manager,
                progress_callback,
                embedding_callback,
                status_callback,
                cancellation_flag,
                expected_missing_count=missing_points,  # Pass expected missing count as keyword arg
                max_retries=DEFAULT_MAX_RETRIES,
                operation_name=f"Migrate missing documents for collection {collection_id}"
            )
            if documents:
                total_documents_migrated += len(documents)
                successful_collections.append({
                    'id': collection_id,
                    'documents': len(documents)
                })
                _log_with_callbacks("info", f"✅ Collection {collection_id} migrated: {len(documents)} missing documents")
            else:
                _log_with_callbacks("warning", f"⚠️ Collection {collection_id}: No missing documents found")
        except Exception as e:
            error_type = type(e).__name__
            error_str = str(e)
            
            # Provide clearer error message for 500 errors
            if "500" in error_str or "Internal Server Error" in error_str:
                if "RocksDB" in error_str:
                    error_summary = f"Qdrant server database error (RocksDB IO error) - Collection: {collection_id}"
                else:
                    error_summary = f"Qdrant server internal error (500) - Collection: {collection_id}"
                _log_with_callbacks("error", f"❌ {error_summary}")
                _log_with_callbacks("error", f"   This is a server-side issue. Check Qdrant server logs and storage.")
            else:
                _log_with_callbacks("error", f"❌ Collection {collection_id} failed: {error_type}: {error_str[:200]}")
            
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            _log_with_callbacks("error", f"Traceback:\n{tb_str}")
            failed_collections.append(collection_id)
    
    _log_with_callbacks("info", f"\n📊 Migration Summary:")
    _log_with_callbacks("info", f"  Total documents migrated: {total_documents_migrated}")
    _log_with_callbacks("info", f"  Successful collections: {len(successful_collections)}")
    _log_with_callbacks("info", f"  Failed collections: {len(failed_collections)}")
    if failed_collections:
        _log_with_callbacks("error", f"  Failed: {', '.join(failed_collections)}")
    
    return {
        'total_documents': total_documents_migrated,
        'successful_collections': successful_collections,
        'failed_collections': failed_collections,
        'total_collections': len(collections),
        'already_synced': len(collections_already_synced)
    }


async def check_collections_sync(qdrant_manager: MultiQdrantManager, check_count: bool = True,
                                 cancellation_flag: Optional[Callable[[], bool]] = None):
    """
    Check if all collections in source are synchronized with target.
    
    Args:
        qdrant_manager: MultiQdrantManager instance
        check_count: Whether to check document counts
    
    Returns:
        Dictionary with sync check results
    """
    _log_with_callbacks("info", "🔍 Checking collections synchronization...")
    _log_with_callbacks("info", f"  Mode: {'Count check' if check_count else 'Existence check'}")
    
    collections = await get_collections_from_mysql()
    _log_with_callbacks("info", f"Found {len(collections)} collections in database")
    
    source_client = qdrant_manager.get_client('default')
    target_client = qdrant_manager.get_client('distributed')
    
    missing_collections = []
    collections_with_missing_points = []
    total_missing_points = 0
    synced_collections = []
    
    for i, collection in enumerate(collections, 1):
        collection_id = collection.id
        _log_with_callbacks("info", f"Checking collection {i}/{len(collections)}: {collection_id}")
        
        try:
            if check_count:
                # Get count from source
                _log_with_callbacks("debug", f"  Collection {collection_id}: Counting documents in source...")
                try:
                    source_count_result = source_client.count(
                        collection_name=SHARED_COLLECTION_NAME,
                        count_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="collection_id",
                                    match=models.MatchValue(value=collection_id)
                                )
                            ]
                        )
                    )
                    source_count = source_count_result.count
                    _log_with_callbacks("debug", f"  Collection {collection_id}: Source count = {source_count}")
                except Exception as e:
                    error_msg = f"Failed to count documents in source for collection {collection_id}: {type(e).__name__}: {str(e)}"
                    _log_with_callbacks("error", error_msg)
                    tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                    raise
                
                if source_count == 0:
                    _log_with_callbacks("warning", f"  Collection {collection_id}: No documents in source, skipping")
                    continue
                
                # Get count from target
                _log_with_callbacks("debug", f"  Collection {collection_id}: Counting documents in target...")
                try:
                    target_count_result = target_client.count(
                        collection_name=SHARED_COLLECTION_NAME,
                        count_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="collection_id",
                                    match=models.MatchValue(value=collection_id)
                                )
                            ]
                        )
                    )
                    target_count = target_count_result.count
                    _log_with_callbacks("debug", f"  Collection {collection_id}: Target count = {target_count}")
                except Exception as e:
                    error_msg = f"Failed to count documents in target for collection {collection_id}: {type(e).__name__}: {str(e)}"
                    _log_with_callbacks("error", error_msg)
                    tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    _log_with_callbacks("error", f"Traceback:\n{tb_str}")
                    raise
                
                if source_count != target_count:
                    missing_points = source_count - target_count
                    total_missing_points += missing_points
                    collections_with_missing_points.append({
                        'collection_id': collection_id,
                        'source_count': source_count,
                        'target_count': target_count,
                        'missing_points': missing_points
                    })
                    _log_with_callbacks("warning", f"  Collection {collection_id}: ⚠️ Missing {missing_points} points (source: {source_count}, target: {target_count})")
                else:
                    synced_collections.append(collection_id)
                    _log_with_callbacks("info", f"  Collection {collection_id}: ✅ Counts match ({source_count} documents)")
            else:
                # Just check if collection exists in target (verify by trying to count)
                _log_with_callbacks("debug", f"  Collection {collection_id}: Checking if exists in target...")
                try:
                    # Verify collection exists by attempting to count (even if we don't use the count)
                    target_client.count(
                        collection_name=SHARED_COLLECTION_NAME,
                        count_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="collection_id",
                                    match=models.MatchValue(value=collection_id)
                                )
                            ]
                        )
                    )
                    synced_collections.append(collection_id)
                    _log_with_callbacks("info", f"  Collection {collection_id}: ✅ Exists in target")
                except Exception as e:
                    # Collection doesn't exist or error accessing it
                    missing_collections.append(collection_id)
                    _log_with_callbacks("warning", f"  Collection {collection_id}: ⚠️ Not found in target: {type(e).__name__}: {str(e)}")
                
        except Exception as e:
            error_msg = f"Error checking collection {collection_id}: {type(e).__name__}: {str(e)}"
            _log_with_callbacks("error", error_msg)
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            _log_with_callbacks("error", f"Traceback:\n{tb_str}")
            missing_collections.append(collection_id)
    
    _log_with_callbacks("info", f"Sync check completed: {len(synced_collections)} synced, {len(collections_with_missing_points)} with missing points, {len(missing_collections)} errors")
    
    return {
        'total_collections': len(collections),
        'synced_collections': synced_collections,
        'missing_collections': missing_collections,
        'collections_with_missing_points': collections_with_missing_points,
        'total_missing_points': total_missing_points
    }

