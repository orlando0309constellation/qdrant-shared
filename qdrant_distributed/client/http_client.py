"""
HTTP client for Qdrant API operations.
"""

import requests
from typing import Dict, Any, Optional

from qdrant_distributed.exceptions import QdrantShardingError
from qdrant_distributed.config import get_qdrant_config


class QdrantHttpClient:
    """Low-level HTTP client for Qdrant API interactions."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        https: Optional[bool] = None
    ):
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for Qdrant instance (e.g., "example.com:6333")
            api_key: Optional API key for authentication
            https: Whether to use HTTPS
        """
        # Get from environment if not provided
        qdrant_url, qdrant_port, self.api_key, qdrant_https = get_qdrant_config(
            url=base_url,
            api_key=api_key,
            https=https
        )
        
        protocol = "https" if qdrant_https else "http"
        self.base_url = f"{protocol}://{qdrant_url}:{qdrant_port}"
        
        # Create a session for connection pooling
        self.session = requests.Session()
        # Set default headers (need to get headers after api_key is set)
        default_headers = {"Content-Type": "application/json"}
        if self.api_key:
            default_headers["api-key"] = self.api_key
        self.session.headers.update(default_headers)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.close()
    
    def close(self):
        """Close the HTTP session."""
        if hasattr(self, 'session') and self.session:
            self.session.close()
    
    def get(
        self,
        endpoint: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request to Qdrant API.
        
        Args:
            endpoint: API endpoint path (e.g., "/cluster")
            timeout: Optional timeout in seconds
        
        Returns:
            Response data as dictionary
        
        Raises:
            QdrantShardingError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        params = {}
        if timeout is not None:
            if timeout <= 0:
                raise ValueError(f"timeout must be positive, got {timeout}")
            params["timeout"] = timeout
        
        try:
            # Use session for connection pooling
            response = self.session.get(
                url,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error occurred: {e}"
            try:
                error_detail = response.json()
                error_msg += f"\nDetails: {error_detail}"
            except:
                pass
            raise QdrantShardingError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            raise QdrantShardingError(
                f"Failed to connect to Qdrant at {url}: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise QdrantShardingError(f"Request timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            raise QdrantShardingError(f"Request failed: {e}") from e
        except ValueError as e:
            raise QdrantShardingError(f"Invalid JSON response: {e}") from e
    
    def post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make a POST request to Qdrant API.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            timeout: Optional timeout in seconds
        
        Returns:
            Response data as dictionary
        
        Raises:
            QdrantShardingError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        params = {}
        if timeout is not None:
            if timeout <= 0:
                raise ValueError(f"timeout must be positive, got {timeout}")
            params["timeout"] = timeout
        
        try:
            # Use session for connection pooling
            response = self.session.post(
                url,
                json=payload,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error occurred: {e}"
            try:
                error_detail = response.json()
                error_msg += f"\nDetails: {error_detail}"
            except:
                pass
            raise QdrantShardingError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            raise QdrantShardingError(
                f"Failed to connect to Qdrant at {url}: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise QdrantShardingError(f"Request timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            raise QdrantShardingError(f"Request failed: {e}") from e
        except ValueError as e:
            raise QdrantShardingError(f"Invalid JSON response: {e}") from e

