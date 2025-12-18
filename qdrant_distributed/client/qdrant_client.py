from typing import Optional

from qdrant_client import AsyncQdrantClient, QdrantClient

from qdrant_distributed.config import (
    get_qdrant_url,
    get_qdrant_port,
    get_qdrant_api_key,
    get_qdrant_https
)

# Module-level defaults for backward compatibility
# Note: https can be None to match original behavior where QdrantClient handles it
qdrant_url = get_qdrant_url()
qdrant_port = get_qdrant_port()
qdrant_api_key = get_qdrant_api_key()
https = get_qdrant_https()  # Can be None, which QdrantClient accepts


class QdrantClientManager:
    """
    Singleton manager for Qdrant clients to ensure proper resource management.
    Provides shared sync and async clients across the application.
    """

    _sync_client: Optional[QdrantClient] = None
    _async_client: Optional[AsyncQdrantClient] = None
    _initialized: bool = False

    @classmethod
    def initialize(
        cls,
        url: str = None,
        api_key: str = None,
        timeout: int = 3600,
        port: str = None,
        https: Optional[bool] = None,
    ) -> None:
        """
        Initialize both sync and async clients.
        Should be called during application startup.
        """
        if cls._initialized:
            return
        
        # Read config dynamically if not provided (allows picking up config changes)
        if url is None:
            url = get_qdrant_url()
        if port is None:
            port = get_qdrant_port()
        if api_key is None:
            api_key = get_qdrant_api_key()
        if https is None:
            https = get_qdrant_https()
        
        print(
            f"Initializing Qdrant clients with url: {url}, api_key: xxx, timeout: {timeout}, port: {port}, https: {https}"
        )
        # Force plaintext HTTP to match current HAProxy config (no TLS termination yet).
        # Avoids SSL WRONG_VERSION_NUMBER when client attempts TLS against HTTP endpoint.
        cls._sync_client = QdrantClient(
            url=url, api_key=api_key, timeout=timeout, port=port, https=https
        )
        cls._async_client = AsyncQdrantClient(
            url=url, api_key=api_key, timeout=timeout, port=port, https=https
        )
        cls._initialized = True

    @classmethod
    def get_sync_client(cls) -> QdrantClient:
        """
        Get the shared sync Qdrant client.
        Raises RuntimeError if not initialized.
        """
        if not cls._initialized or cls._sync_client is None:
            raise RuntimeError(
                "QdrantClientManager not initialized. Call QdrantClientManager.initialize() first."
            )
        return cls._sync_client

    @classmethod
    def get_async_client(cls) -> AsyncQdrantClient:
        """
        Get the shared async Qdrant client.
        Raises RuntimeError if not initialized.
        """
        if not cls._initialized or cls._async_client is None:
            raise RuntimeError(
                "QdrantClientManager not initialized. Call QdrantClientManager.initialize() first."
            )
        return cls._async_client

    @classmethod
    async def close(cls) -> None:
        """
        Close both clients and cleanup resources.
        Should be called during application shutdown.
        """
        if cls._async_client:
            await cls._async_client.close()
            cls._async_client = None

        if cls._sync_client:
            cls._sync_client.close()
            cls._sync_client = None

        cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the client manager is initialized."""
        return cls._initialized
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the client manager by closing existing clients and clearing initialization state.
        This allows re-initialization with new configuration.
        Should be called when configuration changes.
        """
        if cls._sync_client:
            try:
                cls._sync_client.close()
            except Exception:
                pass  # Ignore errors during cleanup
            cls._sync_client = None
        
        if cls._async_client:
            # Note: We can't await in a sync method, so we'll just clear the reference
            # The async client will be properly closed on next async close() call
            cls._async_client = None
        
        cls._initialized = False