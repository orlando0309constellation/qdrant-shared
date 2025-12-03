import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
from yaml import load_all
import argparse
import logging
import os
from datetime import datetime

load_dotenv()

from sqlalchemy.orm import load_only
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[0]))

from src.chat.services.chat_data_stream import get_token_length
from src.configuration.constants import SHARED_COLLECTION_NAME
from src.database.mysql_global import set_ip_address
from src.llm_models.services.openai_models import embedding_small_model
import datetime
set_ip_address()

# Configuration constants for batch processing
DEFAULT_BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", "1000"))  # Default batch size for scroll operations
MAX_BATCH_SIZE = 10000  # Maximum allowed batch size
MIN_BATCH_SIZE = 100    # Minimum allowed batch size
DEFAULT_MAX_RETRIES = int(os.getenv("QDRANT_MAX_RETRIES", "3"))  # Default max retries
DEFAULT_RETRY_DELAY = int(os.getenv("QDRANT_RETRY_DELAY", "2"))  # Default retry delay in seconds

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

async def retry_operation(operation, *args, max_retries: int = DEFAULT_MAX_RETRIES, delay: int = DEFAULT_RETRY_DELAY, **kwargs):
    """Generic retry mechanism for both sync and async operations"""
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(operation):
                return await operation(*args, **kwargs)
            else:
                return operation(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ All {max_retries} attempts failed")
                raise

from src.database.mysql_connector import get_db
from src.ingest.services.vdb_setup import initialize_collection

# Configure professional logging with proper error handling
def setup_logging():
    """Setup logging with fallback mechanism"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Set up handlers list
    handlers = []
    
    # Always add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # Try to add file handler
    try:
        log_file = log_dir / f'migrate_qdrant_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # File gets more detailed logs
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
        print(f"✅ Logging to file: {log_file}")
    except Exception as e:
        print(f"⚠️  Could not set up file logging: {e}")
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=handlers,
        force=True  # This forces reconfiguration if already configured
    )
    
    # Create and test logger
    logger = logging.getLogger(__name__)
    
    # Set specific loggers to avoid spam
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Test the logger
    logger.info("🚀 Logger initialized successfully")
    logger.debug("Debug logging is working")
    
    return logger

# Initialize logging early
logger = setup_logging()

from src.configuration.qdrant_client import QdrantClientManager
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client import models
from typing import Dict, Optional, List, Any
import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import relationship

from src.database.mysql_connector import Base

# Import all models to ensure they are available for SQLAlchemy
from src.abonnement.models.user_abonnement_model import UserAbonnementModel
from src.auth.models.roles import Roles
from src.collection.models.collection import CollectionModel
from src.collection.models.collection_file import CollectionFileModel
from src.collection.models.collection_url import CollectionUrlModel
from src.database.mysql_connector import Base
from src.ia.models.ia_model import IA
from src.jupiter_user.models.jupiter_info import JupiterInfo
from src.jupiter_user.models.jupiter_user import JupiterUser
from src.logs.models.log import Log
from src.logs.models.log_detail import LogDetail
from src.logs.models.log_jupiter import LogJupiter
from src.mail.models.click_counter import ClickCounter
from src.mail.models.mail_campaign_date import MailCampaignDate
from src.myauxs.models.category import Category
from src.myauxs.models.myaux_access import MyAuxAccess
from src.myauxs.models.myaux_collection_import import MyAuxCollectionImport
from src.myauxs.models.myaux_model import MyAuxModel
from src.myauxs.models.prompt_suggestion import PromptSuggestion
from src.notif.models.notif_bo import NotificationBO
from src.notif.models.notif_jupiter import NotificationJupiter
from src.notif.models.payment_alert import PaymentAlert
from src.offer_analysis.models.offer import OfferModel
from src.offer_analysis.models.offer_analysis import OfferAnalysisModel
from src.organization.models.organization_members_model import OrganizationMemberModel
from src.organization.models.organization_model import OrganizationModel
from src.pricing.models.credit_offer import CreditOffer
from src.pricing.models.LogSAP import LogSAP
from src.pricing.models.payment import Payment
from src.pricing.models.plan import Plan
from src.pricing.models.pricing import PricingModel
from src.session.models.session import SessionModel
from src.session.models.session_click import SessionClickCounter
from src.session.models.user_click_counter import UserClickCounter
from src.status.models.status import AppStatus
from src.team.models.team import Team
from src.team.models.team_collection import TeamCollection
from src.team.models.team_collection_member import TeamCollectionMembers
from src.team.models.team_shared_item import TeamSharedItem
from src.token_usage.models.token_usage import TokenUsage
from src.users.models.contact_request import ContactRequest
from src.users.models.country import Country
from src.users.models.eviction import Eviction
from src.users.models.invitation import Invitation
from src.users.models.user import User
from src.users.models.user_active_token import UserActiveToken

from src.project.models.project import Project
from src.project.models.project_collection import ProjectCollection
from src.project.models.project_agent import ProjectAgent
from src.project.models.project_favorite import ProjectFavorite
from src.myauxs.models.myaux_category_assignment import MyauxCategoryAssignement
from src.myauxs.models.myaux_pin import MyAuxPin
from src.project.models.project_access import ProjectAccess
from src.project.models.project_category import ProjectCategory
from src.project.models.project_category_assignment import ProjectCategoryAssignement
from src.project.models.project_collection_status import ProjectCollectionStatus
from src.project.models.project_personal_agent import ProjectPersonalAgent


class MultiQdrantManager:
    """Manager for multiple Qdrant instances"""
    
    def __init__(self,https:bool =False):
        self.clients: Dict[str, QdrantClient] = {}
        self.async_clients: Dict[str, AsyncQdrantClient] = {}
        self.https = https
        
    def add_client(self, name: str, url: str, port: int, api_key: Optional[str] = None, timeout: int = 3600, https: bool = None) -> QdrantClient:
        """Add a new sync Qdrant client"""
        try:
            client = QdrantClient(
                url=url,
                port=port,
                api_key=api_key,
                timeout=timeout,
                https=https if https is not None else self.https  # Force HTTP to avoid SSL issues
            )
            self.clients[name] = client
            logger.info(f"✅ Added sync Qdrant client '{name}' for {url}:{port}")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to add sync Qdrant client '{name}': {e}")
            raise
    
    def add_async_client(self, name: str, url: str, port: int, api_key: Optional[str] = None, timeout: int = 3600, https: bool = None) -> AsyncQdrantClient:
        """Add a new async Qdrant client"""
        try:
            from qdrant_client import AsyncQdrantClient
            client = AsyncQdrantClient(
                url=url,
                port=port,
                api_key=api_key,
                timeout=timeout,
                https=https if https is not None else self.https  # Force HTTP to avoid SSL issues
            )
            self.async_clients[name] = client
            logger.info(f"✅ Added async Qdrant client '{name}' for {url}:{port}")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to add async Qdrant client '{name}': {e}")
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
    
    def list_clients(self):
        """List all available clients"""
        logger.info(f"Available sync Qdrant clients: {list(self.clients.keys())}")
        for name, client in self.clients.items():
            try:
                logger.info(f"  - {name}: {client._client.url}")
            except AttributeError:
                logger.info(f"  - {name}: <client info not available>")
        
        logger.info(f"Available async Qdrant clients: {list(self.async_clients.keys())}")
        for name, client in self.async_clients.items():
            try:
                logger.info(f"  - {name}: {client._client.url}")
            except AttributeError:
                logger.info(f"  - {name}: <client info not available>")
    
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
        # Note: async clients will be closed separately in close_async_clients()
    
    async def close_async_clients(self):
        """Close all async clients properly"""
        for name, client in self.async_clients.items():
            try:
                await client.close()
                logger.info(f"Closed async client: {name}")
            except Exception as e:
                logger.warning(f"Error closing async client {name}: {e}")
        self.async_clients.clear()


async def force_initialize_distributed_collection(distributed_async_client, max_retries: int = 5):
    """Force initialize distributed collection with retries"""
    logger.info("🚀 Force initializing distributed collection...")
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to initialize distributed collection...")
            
            # Try the normal initialization
            await initialize_collection(distributed_async_client)
            logger.info("✅ Successfully initialized distributed collection")
            return
            
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                # Wait longer between retries for consensus issues
                wait_time = 10 * (attempt + 1)  # 10, 20, 30, 40 seconds
                logger.info(f"Waiting {wait_time} seconds before retry (consensus recovery time)...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Failed to initialize distributed collection after {max_retries} attempts: {e}")
                raise


async def main(mode: str = "migrate", check_count: bool = False, https: bool = True, reverse: bool = False):
    try:
        logger.info(f"🚀 Starting Qdrant migration tool in mode: {mode}")
        logger.debug(f"Debug logging is enabled. Mode: {mode}, Check count: {check_count}")
        
        # Initialize the default Qdrant instance (from environment variables)
        QdrantClientManager.initialize()
        logger.info("✅ Initialized shared Qdrant clients")
        
        # Create a multi-instance manager
        qdrant_manager = MultiQdrantManager(https=https)
        
        # Add the default sync client to our manager
        default_client = QdrantClientManager.get_sync_client()
        qdrant_manager.clients['default'] = default_client
        logger.debug("Added default sync client to manager")
        
        # Add the default async client to our manager
        default_async_client = QdrantClientManager.get_async_client()
        qdrant_manager.async_clients['default_async'] = default_async_client
        logger.debug("Added default async client to manager")
        
        # Add the distributed instance for receiving documents (but not for initialization)
        second_qdrant_url = os.getenv("QDRANT_URL_2", "localhost")
        second_qdrant_port = int(os.getenv("QDRANT_PORT_2", "6333"))
        second_qdrant_api_key = os.getenv("QDRANT_API_KEY_2", os.getenv("QDRANT_API_KEY", ""))
        
        logger.info(f"Configuring distributed instance: {second_qdrant_url}:{second_qdrant_port}")
        qdrant_manager.add_client(
            name="distributed",
            url=second_qdrant_url,
            port=second_qdrant_port,
            api_key=second_qdrant_api_key,
            https=True
        )
        
        # Also add async client for distributed instance for initialization
        qdrant_manager.add_async_client(
            name="distributed_async",
            url=second_qdrant_url,
            port=second_qdrant_port,
            api_key=second_qdrant_api_key,
            https=True
        )
        if reverse:
            # Swap clients: distributed becomes source (default), default becomes destination (distributed)
            qdrant_manager.clients['default'] = qdrant_manager.get_client('distributed')
            qdrant_manager.async_clients['default_async'] = qdrant_manager.get_async_client('distributed_async')
            qdrant_manager.clients['distributed'] = default_client  
            qdrant_manager.async_clients['distributed_async'] = default_async_client
            logger.info("🔄 Reverse mode enabled: migrating from distributed to default instance")
            

        
        # List all available clients
        qdrant_manager.list_clients()
        
        if mode == "migrate":
            logger.info("🔄 Running in MIGRATE mode - migrating all collections without checks")
            # Use only the default instance to avoid consensus issues
            default_instance = qdrant_manager.get_client('default')
            default_async_instance = qdrant_manager.get_async_client('default_async')
            distributed_async_instance = qdrant_manager.get_async_client('distributed_async')
            
            # Initialize collections using async clients
            await initialize_collection(default_async_instance)
            logger.info("✅ Initialized Qdrant default collections")
            
            # Force initialize distributed collection with retries
            await force_initialize_distributed_collection(distributed_async_instance)
            logger.info("✅ Initialized Qdrant distributed collections")
            
            # Wait a moment for collection to be fully available
            logger.info("⏳ Waiting for collection to be fully available...")
            await asyncio.sleep(5)



            await migrate(qdrant_manager)
            
        elif mode == "migrate-usc":
            logger.info("🔍 Running in MIGRATE-USC mode - migrating only after necessary checks")
            # Use only the default instance to avoid consensus issues
            default_instance = qdrant_manager.get_client('default')
            default_async_instance = qdrant_manager.get_async_client('default_async')
            distributed_async_instance = qdrant_manager.get_async_client('distributed_async')
            
            # Initialize collections using async clients
            await initialize_collection(default_async_instance)
            logger.info("✅ Initialized Qdrant default collections")
            
            # Force initialize distributed collection with retries
            await force_initialize_distributed_collection(distributed_async_instance)
            logger.info("✅ Initialized Qdrant distributed collections")
            
            # Wait a moment for collection to be fully available
            logger.info("⏳ Waiting for collection to be fully available...")
            await asyncio.sleep(5)

            await migrate_with_checks(qdrant_manager)
            
        elif mode == "check":
            logger.info("🔍 Running in CHECK mode - verifying synchronization")
            await check_collections_sync(qdrant_manager, check_count)
        
        logger.info("🧹 Starting cleanup process...")
        
        # Clean up
        qdrant_manager.close_all()
        await qdrant_manager.close_async_clients()
        
        # Close database connections gracefully
        try:
            from src.database.mysql_connector import close_db_connections
            await close_db_connections()
            logger.debug("Closed database connections")
        except Exception as e:
            logger.warning(f"Error closing database connections: {e}")
        
        # Close QdrantClientManager gracefully
        try:
            await QdrantClientManager.close()
            logger.debug("Closed QdrantClientManager")
        except Exception as e:
            logger.warning(f"Error closing QdrantClientManager: {e}")
        
        logger.info("✅ Migration tool completed successfully")
        
    except Exception as e:
        logger.exception(f"❌ Fatal error in main: {e}")
        raise

async def general_summary(collection_id: str, documents: List[Any]):
    """
    Create general summaries for each source group and save them as new points.
    
    Args:
        collection_id: The collection ID to process
        documents: List of documents from the collection
    """
    try:
        logger.info(f"🔄 Creating general summaries for collection: {collection_id}")
        
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
            
            # Create summary point for this source
            summary_point = models.PointStruct(
                id=f"{uuid.uuid4()}",
                vector={
                    "dense": await embedding_small_model.aembed_query(combined_content),
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
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                },
            )
            
            summary_points.append(summary_point)
            logger.info(f"Created summary for {source}: {len(source_docs)} docs, {total_tokens} tokens")
        
        return summary_points
        
    except Exception as e:
        logger.exception(f"Error creating general summaries for collection {collection_id}: {e}")
        raise

async def save_summaries(qdrant_manager: MultiQdrantManager, collection_id: str, summary_points: List[models.PointStruct]):
    """
    Save general summary points to the distributed instance.
    Efficiently checks existing summaries with a single scroll operation.
    
    Args:
        qdrant_manager: The Qdrant manager instance
        collection_id: The collection ID
        summary_points: List of summary points to save
    """
    try:
        if not summary_points:
            logger.info(f"No summary points to save for collection {collection_id}")
            return
        
        logger.info(f"💾 Checking existing summaries for collection {collection_id}")
        
        # Get the distributed client
        distributed_client = qdrant_manager.get_client('distributed')
        
        # Load all existing summaries for this collection in one operation
        existing_summaries = {}  # key: source, value: page_content
        offset = None
        
        while True:
            try:
                # Scroll to get all existing summaries for this collection
                search_result = distributed_client.scroll(
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
                    limit=1000,  # Large batch to get all at once
                    offset=offset
                )
                
                documents = search_result[0]
                next_page_offset = search_result[1]
                
                if not documents:
                    break
                
                # Build dictionary of existing summaries
                for doc in documents:
                    source = doc.payload.get('metadata', {}).get('source', 'unknown')
                    page_content = doc.payload.get('page_content', '')
                    if source and page_content:  # Only add if both exist and not null
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
            
            # Check if summary already exists with same content
            if source in existing_summaries and existing_summaries[source] == page_content:
                logger.info(f"Summary for source {source} already exists with same content, skipping")
            else:
                new_summary_points.append(point)
        
        if not new_summary_points:
            logger.info(f"All summaries for collection {collection_id} already exist")
            return
        
        logger.info(f"💾 Saving {len(new_summary_points)} new summary points")
        
        # Save new summary points
        await retry_operation(
            distributed_client.upsert,
            collection_name=SHARED_COLLECTION_NAME,
            points=new_summary_points,
            max_retries=3
        )
        
        logger.info(f"✅ Successfully saved {len(new_summary_points)} summary points for collection {collection_id}")
        
    except Exception as e:
        logger.exception(f"Error saving summaries for collection {collection_id}: {e}")
        raise

async def process_collection(collection_id: str, qdrant_manager: MultiQdrantManager):
    """Process a collection by checking default Qdrant and sending to distributed instance"""
    try:
        logger.info(f"🔄 Processing collection: {collection_id}")
        
        # Get the default Qdrant client from the manager
        default_client = qdrant_manager.get_client('default')
        
        # Use configurable batch size for better performance
        batch_size = get_batch_size()
        logger.info(f"Using batch size: {batch_size}")
        
        offset = None
        all_documents = []
        total_documents = 0
        
        while True:
            logger.debug(f"Fetching batch for collection {collection_id}, offset: {offset}")
            
            # Fetch documents in batches
            search_result = default_client.scroll(
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
            
            documents = search_result[0]  # First element contains the points
            next_page_offset = search_result[1]  # Next page offset
            
            if not documents:
                logger.debug(f"No more documents for collection {collection_id}")
                break
                
            all_documents.extend(documents)
            total_documents += len(documents)
            logger.info(f"Fetched {len(documents)} documents (total: {total_documents}) for collection_id: {collection_id}")
            
            # Prepare points for the distributed instance
            points = []
            points_number = len(documents)
            for doc in documents:
                point = models.PointStruct(
                    id=doc.id,
                    vector=doc.vector,
                    payload=doc.payload
                )
                if "metadata" not in point.payload:
                    point.payload["metadata"] = {}
                point.payload["metadata"]["points_number"] = points_number
                point.payload["metadata"]["tokens"] = get_token_length(doc.payload["page_content"], "cl100k_base")
                
                points.append(point)
            
            # Send documents to the distributed instance with retry
            distributed_client = qdrant_manager.get_client('distributed')
            try:
                await retry_operation(
                    distributed_client.upsert,
                    collection_name=SHARED_COLLECTION_NAME,
                    points=points,
                    max_retries=3
                )
            except Exception as e:
                logger.error(f"Failed to upsert batch after retries: {e}")
                raise
            
            logger.info(f"✅ Sent batch of {len(points)} documents to distributed instance")
            logger.debug(f"Batch details: points_number={points_number}, documents_in_batch={len(documents)}")
            
            # Update offset for next batch
            if next_page_offset is None:
                logger.debug(f"Reached end of collection {collection_id}")
                break
            offset = next_page_offset
        
        # NEW: Create general summaries for each source group
        logger.info(f"⌛ Creating general summaries for collection {collection_id}")
        summary_points = await general_summary(collection_id, all_documents)
        
        # NEW: Save the summary points
        if summary_points:
            await save_summaries(qdrant_manager, collection_id, summary_points)
        
        logger.info(f"✅ Successfully processed collection {collection_id}: {total_documents} documents sent to distributed instance")
        return all_documents
        
    except Exception as e:
        logger.exception(f"Error processing collection {collection_id}: {e}")
        raise  # Re-raise to trigger retry mechanism

async def migrate(qdrant_manager: MultiQdrantManager):
    """Migrate all collections without checking what's already in distributed"""
    collections = await get_collections()
    logger.info(f"Found {len(collections)} collections to migrate")
    logger.info("=" * 60)
    
    total_documents_migrated = 0
    failed_collections = []
    
    for i, collection in enumerate(collections, 1):
        logger.info(f"🔄 Processing collection {i}/{len(collections)}: {collection.id}")
        try:
            # Process each collection with retry mechanism
            try:
                documents = await retry_operation(
                    process_collection, 
                    collection.id, 
                    qdrant_manager,
                    max_retries=DEFAULT_MAX_RETRIES
                )
            except Exception as e:
                logger.error(f"❌ All {DEFAULT_MAX_RETRIES} attempts failed for collection {collection.id}: {e}")
                documents = []
            if documents:
                total_documents_migrated += len(documents)
                logger.info(f"✅ Collection {collection.id} migrated: {len(documents)} documents sent to distributed instance")
            else:
                logger.warning(f"⚠️  Collection {collection.id}: No documents found")
        except Exception as e:
            logger.exception(f"❌ Collection {collection.id} failed after all retries: {e}")
            failed_collections.append(collection.id)
        logger.info("-" * 50)
    
    logger.info(f"🎉 Migration completed!")
    logger.info(f"Total documents migrated: {total_documents_migrated}")
    if failed_collections:
        logger.error(f"Failed collections ({len(failed_collections)}): {failed_collections}")
    else:
        logger.info("✅ All collections migrated successfully!")
    logger.info("=" * 60)

async def create_summaries_for_synced_collections(qdrant_manager: MultiQdrantManager, synced_collection_ids: List[str]):
    """
    Create general summaries for collections that are already synchronized.
    
    Args:
        qdrant_manager: The Qdrant manager instance
        synced_collection_ids: List of collection IDs that are already synchronized
    """
    try:
        logger.info(f"🔄 Creating summaries for {len(synced_collection_ids)} synchronized collections")
        
        distributed_client = qdrant_manager.get_client('distributed')
        
        for collection_id in synced_collection_ids:
            try:
                logger.info(f"📝 Processing collection {collection_id} for summary creation")
                
                # Get all documents for this collection from distributed instance
                all_documents = []
                offset = None
                batch_size = get_batch_size()
                
                while True:
                    search_result = distributed_client.scroll(
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
                        break
                    
                    all_documents.extend(documents)
                    
                    if next_page_offset is None:
                        break
                    offset = next_page_offset
                
                if not all_documents:
                    logger.warning(f"No documents found for collection {collection_id}")
                    continue
                
                logger.info(f"Found {len(all_documents)} documents for collection {collection_id}")
                
                # Create general summaries for this collection
                summary_points = await general_summary(collection_id, all_documents)
                
                # Save the summary points
                if summary_points:
                    await save_summaries(qdrant_manager, collection_id, summary_points)
                    logger.info(f"✅ Created summaries for collection {collection_id}")
                else:
                    logger.warning(f"No summary points created for collection {collection_id}")
                    
            except Exception as e:
                logger.exception(f"Error creating summaries for collection {collection_id}: {e}")
                continue
        
        logger.info(f"✅ Completed summary creation for synchronized collections")
        
    except Exception as e:
        logger.exception(f"Error in create_summaries_for_synced_collections: {e}")
        raise

async def migrate_with_checks(qdrant_manager: MultiQdrantManager):
    """Migrate only specific missing documents after checking what's already in distributed"""
    logger.info("🔍 Starting migration with necessary checks...")
    
    # First, check what needs to be migrated
    collections = await get_collections()
    logger.info(f"Found {len(collections)} collections in database")
    
    default_client = qdrant_manager.get_client('default')
    distributed_client = qdrant_manager.get_client('distributed')
    distributed_collection_name = SHARED_COLLECTION_NAME
    
    # Verify distributed collection exists
    try:
        distributed_client.get_collection(distributed_collection_name)
        logger.info(f"✅ Distributed collection '{distributed_collection_name}' exists")
    except Exception as e:
        logger.error(f"❌ Distributed collection '{distributed_collection_name}' does not exist: {e}")
        return
    
    collections_to_migrate = []
    collections_already_synced = []
    
    # Check each collection to see if it needs migration
    for i, collection in enumerate(collections, 1):
        collection_id = collection.id
        logger.info(f"🔍 Checking collection {i}/{len(collections)}: {collection_id}")
        
        try:
            # Get count of documents in default instance
            default_count_result = default_client.count(
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
            default_count = default_count_result.count
            logger.debug(f"  Default instance count for {collection_id}: {default_count}")
            
            if default_count == 0:
                logger.warning(f"  ⚠️  No documents in default instance for collection {collection_id}")
                continue
            
            # Get count of documents in distributed instance
            distributed_count_result = distributed_client.count(
                collection_name=distributed_collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="collection_id",
                            match=models.MatchValue(value=collection_id)
                        )
                    ]
                )
            )
            distributed_count = distributed_count_result.count
            logger.debug(f"  Distributed instance count for {collection_id}: {distributed_count}")
            
            if default_count != distributed_count:
                missing_points = default_count - distributed_count
                collections_to_migrate.append({
                    'collection_id': collection_id,
                    'default_count': default_count,
                    'distributed_count': distributed_count,
                    'missing_points': missing_points
                })
                logger.warning(f"  ⚠️  Collection {collection_id} needs migration: {missing_points} points missing")
            else:
                collections_already_synced.append(collection_id)
                logger.info(f"  ✅ Collection {collection_id} is already synchronized")
                
        except Exception as e:
            logger.exception(f"  ❌ Error checking collection {collection_id}: {e}")
            # If we can't check, assume it needs migration
            collections_to_migrate.append({
                'collection_id': collection_id,
                'default_count': 0,
                'distributed_count': 0,
                'missing_points': 0
            })
    
    # Summary of what needs to be done
    logger.info("\n" + "=" * 60)
    logger.info("📊 MIGRATION ANALYSIS SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Collections already synchronized: {len(collections_already_synced)}")
    logger.info(f"Collections needing migration: {len(collections_to_migrate)}")
    
    if collections_already_synced:
        logger.info("✅ Already synchronized collections:")
        for coll_id in collections_already_synced:
            logger.info(f"   - {coll_id}")
        
        # Create general summaries for already synchronized collections
        logger.info(f"🔄 Creating general summaries for {len(collections_already_synced)} already synchronized collections...")
        await create_summaries_for_synced_collections(qdrant_manager, collections_already_synced)
    
    if collections_to_migrate:
        total_missing = sum(item['missing_points'] for item in collections_to_migrate)
        logger.info(f"🔄 Collections to migrate (total missing points: {total_missing}):")
        for item in collections_to_migrate:
            logger.info(f"   - {item['collection_id']}: {item['missing_points']} missing points")
    
    # Proceed with migration only for collections that need it
    if not collections_to_migrate:
        logger.info("🎉 All collections are already synchronized! No migration needed.")
        return
    
    logger.info("\n🚀 Starting selective migration of missing documents only...")
    logger.info("=" * 60)
    
    total_documents_migrated = 0
    failed_collections = []
    
    for i, migration_item in enumerate(collections_to_migrate, 1):
        collection_id = migration_item['collection_id']
        missing_points = migration_item['missing_points']
        
        logger.info(f"🔄 Migrating missing documents {i}/{len(collections_to_migrate)} for collection: {collection_id} (missing {missing_points} points)")
        try:
            # Process only missing documents for this collection
            try:
                documents = await retry_operation(
                    process_collection_missing_only, 
                    collection_id, 
                    qdrant_manager,
                    max_retries=DEFAULT_MAX_RETRIES
                )
            except Exception as e:
                logger.error(f"❌ All {DEFAULT_MAX_RETRIES} attempts failed for collection {collection_id}: {e}")
                documents = []
            if documents:
                total_documents_migrated += len(documents)
                logger.info(f"✅ Collection {collection_id} migrated: {len(documents)} missing documents sent to distributed instance")
            else:
                logger.warning(f"⚠️  Collection {collection_id}: No missing documents found")
        except Exception as e:
            logger.exception(f"❌ Collection {collection_id} failed after all retries: {e}")
            failed_collections.append(collection_id)
        logger.info("-" * 50)
    
    logger.info(f"🎉 Selective migration completed!")
    logger.info(f"Total missing documents migrated: {total_documents_migrated}")
    if failed_collections:
        logger.error(f"Failed collections ({len(failed_collections)}): {failed_collections}")
    else:
        logger.info("✅ All collections migrated successfully!")
    logger.info("=" * 60)

async def process_collection_missing_only(collection_id: str, qdrant_manager: MultiQdrantManager):
    """Process only missing documents for a collection using the same batch logic as process_collection"""
    try:
        logger.info(f"🔄 Processing missing documents for collection: {collection_id}")
        
        # Get the default Qdrant client from the manager
        default_client = qdrant_manager.get_client('default')
        
        # Get all document IDs from distributed instance for this collection (to know what's already there)
        distributed_client = qdrant_manager.get_client('distributed')
        logger.debug(f"Fetching existing documents from distributed instance for collection {collection_id}")
        
        # Use configurable batch size for fetching existing documents
        batch_size = get_batch_size()
        logger.info(f"Using batch size: {batch_size}")
        
        # Fetch existing documents in batches to avoid memory issues
        existing_distributed_ids = set()
        offset = None
        
        while True:
            logger.debug(f"Fetching existing documents batch, offset: {offset}")
            try:
                distributed_docs_result = distributed_client.scroll(
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
                
                distributed_docs = distributed_docs_result[0]
                next_page_offset = distributed_docs_result[1]
                
                if not distributed_docs:
                    break
                    
                existing_distributed_ids.update(doc.id for doc in distributed_docs)
                logger.debug(f"Fetched {len(distributed_docs)} existing documents in this batch")
                
                if next_page_offset is None:
                    break
                offset = next_page_offset
                
            except Exception as e:
                logger.warning(f"Error fetching existing documents batch: {e}")
                break
        
        logger.info(f"  Found {len(existing_distributed_ids)} existing documents in distributed instance")
        
        # Now process missing documents with batch size
        offset = None
        all_missing_documents = []
        total_documents = 0
        
        while True:
            logger.debug(f"Fetching batch for missing documents, collection {collection_id}, offset: {offset}")
            
            # Fetch documents in batches
            search_result = default_client.scroll(
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
            
            documents = search_result[0]  # First element contains the points
            next_page_offset = search_result[1]  # Next page offset
            
            if not documents:
                logger.debug(f"No more documents for collection {collection_id}")
                break
            
            # Filter out documents that already exist in distributed
            missing_documents = [doc for doc in documents if doc.id not in existing_distributed_ids]
            logger.debug(f"Found {len(missing_documents)} missing documents in this batch")
            
            if missing_documents:
                # Prepare points for the distributed instance
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
                    point.payload["metadata"]["tokens"] = get_token_length(doc.payload["page_content"], "cl100k_base")
                    
                    points.append(point)
                
                # Send missing documents to the distributed instance with retry
                try:
                    await retry_operation(
                        distributed_client.upsert,
                        collection_name=SHARED_COLLECTION_NAME,
                        points=points,
                        max_retries=3
                    )
                except Exception as e:
                    logger.error(f"Failed to upsert missing documents batch after retries: {e}")
                    raise
                
                all_missing_documents.extend(missing_documents)
                total_documents += len(missing_documents)
                logger.info(f"✅ Sent batch of {len(points)} missing documents to distributed instance")
                logger.debug(f"Missing batch details: points_number={points_number}, missing_docs_in_batch={len(missing_documents)}")
            else:
                logger.debug(f"  Batch has no missing documents, skipping...")
            
            # Update offset for next batch
            if next_page_offset is None:
                logger.debug(f"Reached end of collection {collection_id}")
                break
            offset = next_page_offset
        
        # NEW: Create general summaries for each source group
        logger.info(f"⌛ Creating general summaries for collection {collection_id}")
        summary_points = await general_summary(collection_id, all_missing_documents)
        
        # NEW: Save the summary points
        if summary_points:
            await save_summaries(qdrant_manager, collection_id, summary_points)
        
        logger.info(f"✅ Successfully processed collection {collection_id}: {total_documents} missing documents sent to distributed instance")
        return all_missing_documents
        
    except Exception as e:
        logger.exception(f"Error processing missing documents for collection {collection_id}: {e}")
        raise  # Re-raise to trigger retry mechanism

async def check_collections_sync(qdrant_manager: MultiQdrantManager, check_count: bool = True):
    """Check if all collections in default are in distributed and optionally count missing points"""
    logger.info("🔍 Checking collections synchronization between default and distributed instances...")
    
    # Get collections from database
    collections = await get_collections()
    logger.info(f"Found {len(collections)} collections in database")
    
    default_client = qdrant_manager.get_client('default')
    distributed_client = qdrant_manager.get_client('distributed')
    distributed_collection_name = SHARED_COLLECTION_NAME
    
    missing_collections = []
    collections_with_missing_points = []
    total_missing_points = 0
    
    for i, collection in enumerate(collections, 1):
        collection_id = collection.id
        logger.info(f"\nChecking collection {i}/{len(collections)}: {collection_id}")
        
        try:
            # Check if collection exists in distributed instance
            try:
                distributed_client.get_collection(distributed_collection_name)
                logger.debug(f"Distributed collection '{distributed_collection_name}' exists")
            except Exception as e:
                logger.error(f"❌ Distributed collection '{distributed_collection_name}' does not exist: {e}")
                return
            
            # Get count of documents in default instance
            default_count_result = default_client.count(
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
            default_count = default_count_result.count
            logger.info(f"  Default instance count: {default_count}")
            
            if default_count == 0:
                logger.warning(f"  ⚠️  No documents in default instance for collection {collection_id}")
                continue
            
            if check_count:
                # Get count of documents in distributed instance
                distributed_count_result = distributed_client.count(
                    collection_name=distributed_collection_name,
                    count_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection_id",
                                match=models.MatchValue(value=collection_id)
                            )
                        ]
                    )
                )
                distributed_count = distributed_count_result.count
                logger.info(f"  Distributed instance count: {distributed_count}")
                
                if default_count != distributed_count:
                    missing_points = default_count - distributed_count
                    total_missing_points += missing_points
                    collections_with_missing_points.append({
                        'collection_id': collection_id,
                        'default_count': default_count,
                        'distributed_count': distributed_count,
                        'missing_points': missing_points
                    })
                    logger.warning(f"  ⚠️  Missing {missing_points} points in distributed instance")
                else:
                    logger.info(f"  ✅ Counts match for collection {collection_id}")
                
        except Exception as e:
            logger.exception(f"  ❌ Error checking collection {collection_id}: {e}")
            missing_collections.append(collection_id)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SYNCHRONIZATION CHECK SUMMARY")
    logger.info("=" * 60)
    
    if missing_collections:
        logger.error(f"❌ Collections with errors during check ({len(missing_collections)}): {missing_collections}")
    
    if check_count and collections_with_missing_points:
        logger.warning(f"⚠️  Collections with missing points ({len(collections_with_missing_points)}):")
        for item in collections_with_missing_points:
            logger.warning(f"   - {item['collection_id']}: {item['missing_points']} missing points "
                  f"(default: {item['default_count']}, distributed: {item['distributed_count']})")
        logger.warning(f"Total missing points across all collections: {total_missing_points}")
    elif check_count:
        logger.info("✅ All collections have matching document counts!")
    
    if not missing_collections and (not check_count or not collections_with_missing_points):
        logger.info("✅ All collections are synchronized!")
    
    logger.info("=" * 60)

async def get_collections():
    try:
        logger.debug("Fetching collections from database...")
        async with get_db() as db:
            stmt = select(CollectionModel).options(load_only(CollectionModel.id, CollectionModel.collection_name))
            result = await db.execute(stmt)
            collections = result.scalars().all()
            logger.info(f"Retrieved {len(collections)} collections from database")
            return collections
    except Exception as e:
        logger.exception(f"Error fetching collections from database: {e}")
        raise


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Qdrant Collection Migration and Synchronization Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_qdrant.py --mode migrate              # Migrate all collections
  python migrate_qdrant.py --mode migrate-usc          # Migrate only missing collections
  python migrate_qdrant.py --mode check --check-count  # Check synchronization with counts
  python migrate_qdrant.py --mode check                # Quick sync check without counts
        """
    )
    parser.add_argument(
        "-m",
        "--mode", 
        type=str, 
        choices=["migrate", "migrate-usc", "check"], 
        default="migrate", 
        help="Mode of operation: 'migrate' to migrate all collections, 'migrate-usc' to migrate only after necessary checks, 'check' to verify synchronization"
    )
    parser.add_argument(
        "--check-count", 
        action="store_true", 
        help="When in 'check' mode, also count and report missing points in distributed instance"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging for more detailed output"
    )

    parser.add_argument(
        "--https",
        default=True,
        type=bool
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse migration direction: migrate from distributed to default instead of default to distributed"
    )
    
    args = parser.parse_args()
    
    # Adjust logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Debug logging enabled")
    
    # Set event loop policy for Windows to avoid issues
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.debug("Set Windows ProactorEventLoopPolicy")
    
    logger.info(f"Starting application with args: mode={args.mode}, check_count={args.check_count}, debug={args.debug}")
    
    try:
        asyncio.run(main(mode=args.mode, check_count=args.check_count, https=args.https, reverse=args.reverse))
        logger.info("🎉 Application completed successfully")
    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted by user")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except asyncio.CancelledError:
        logger.info("🛑 Process was cancelled")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
    
    # Suppress cleanup errors that occur after the event loop is closed
    import warnings
    warnings.filterwarnings("ignore", message="Exception ignored in.*Event loop is closed")