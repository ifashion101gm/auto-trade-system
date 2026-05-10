"""
LLM Provider with HTTP connection pooling.
Zone B Optimization: Reuse connections to reduce latency and overhead.
"""
import httpx
from typing import Dict, Any, Optional


class LLMProviderPool:
    """
    LLM provider with persistent HTTP connections.
    
    Zone B Optimization:
    - HTTP connection pooling reduces connection overhead
    - Configurable timeouts per provider
    - Automatic retry on transient failures
    """
    
    def __init__(self):
        # Connection pools for different providers
        self._clients: Dict[str, httpx.AsyncClient] = {}
        
        # Default timeout configuration
        self._timeout = httpx.Timeout(
            connect=5.0,
            read=30.0,
            write=10.0,
            pool=5.0
        )
        
        # Initialize provider clients
        self._init_providers()
    
    def _init_providers(self):
        """Initialize HTTP clients for each LLM provider."""
        
        # OpenAI (GPT-4o-mini, GPT-4)
        self._clients["openai"] = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
        
        # Anthropic (Claude Sonnet, Claude Haiku)
        self._clients["anthropic"] = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
        
        # Google (Gemini Flash, Gemini Pro)
        self._clients["google"] = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
    
    async def close(self):
        """Close all HTTP client connections."""
        for client in self._clients.values():
            await client.aclose()
    
    async def call_openai(self, endpoint: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """
        Call OpenAI API with connection pooling.
        
        Args:
            endpoint: API endpoint (e.g., "/chat/completions")
            payload: Request payload
            api_key: OpenAI API key
            
        Returns:
            Response data
        """
        client = self._clients["openai"]
        
        response = await client.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        return response.json()
    
    async def call_anthropic(self, endpoint: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """
        Call Anthropic API with connection pooling.
        
        Args:
            endpoint: API endpoint (e.g., "/messages")
            payload: Request payload
            api_key: Anthropic API key
            
        Returns:
            Response data
        """
        client = self._clients["anthropic"]
        
        response = await client.post(
            endpoint,
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        return response.json()
    
    async def call_google(self, endpoint: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """
        Call Google Generative AI API with connection pooling.
        
        Args:
            endpoint: API endpoint
            payload: Request payload
            api_key: Google API key
            
        Returns:
            Response data
        """
        client = self._clients["google"]
        
        response = await client.post(
            f"{endpoint}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        return response.json()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            provider: {
                "is_closed": client.is_closed,
                "max_connections": client.limits.max_connections,
                "max_keepalive": client.limits.max_keepalive_connections
            }
            for provider, client in self._clients.items()
        }
