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
        self.base_url = f"{qdrant_url}:{qdrant_port}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers
    
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
            response = requests.get(
                url,
                headers=self._get_headers(),
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
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
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

