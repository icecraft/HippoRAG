"""
OpenAI client factory for HippoRAG.

Provides unified client creation for both LLM and embedding services.
Supports OpenAI-compatible APIs (Dashscope, Silicon, etc.)
"""
import os
from typing import Optional

import httpx
from openai import OpenAI

from .utils.logging_utils import get_logger

logger = get_logger(__name__)


class OpenAIClientFactory:
    """
    Factory for creating OpenAI clients.

    Supports:
    - OpenAI official API
    - OpenAI-compatible services (Dashscope, Silicon, etc.)
    """

    @staticmethod
    def create(
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        high_throughput: bool = False,
        max_retries: int = 2,
        timeout: int = 300,
    ) -> OpenAI:
        """
        Create an OpenAI client.

        Parameters:
            base_url: API base URL (defaults to OPENAI_BASE_URL env var)
            api_key: API key (defaults to OPENAI_API_KEY env var)
            high_throughput: Enable high throughput with more connections
            max_retries: Maximum retries for failed requests
            timeout: Request timeout in seconds

        Returns:
            Configured OpenAI client
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
            )

        # Configure HTTP client for high throughput
        http_client = None
        if high_throughput:
            limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
            http_client = httpx.Client(
                limits=limits,
                timeout=httpx.Timeout(timeout, read=timeout)
            )

        # Build client kwargs
        client_kwargs = {
            "api_key": api_key,
            "max_retries": max_retries,
        }

        if base_url:
            client_kwargs["base_url"] = base_url

        if http_client:
            client_kwargs["http_client"] = http_client

        logger.debug(f"Creating OpenAI client: base_url={base_url}, high_throughput={high_throughput}")

        return OpenAI(**client_kwargs)

    @staticmethod
    def create_for_llm(
        base_url: Optional[str] = None,
        max_retries: int = 2,
        **kwargs
    ) -> OpenAI:
        """
        Create OpenAI client for LLM operations (chat completions).

        Enables high throughput by default for batch processing.
        """
        return OpenAIClientFactory.create(
            base_url=base_url,
            high_throughput=kwargs.pop("high_throughput", True),
            max_retries=max_retries,
            **kwargs
        )

    @staticmethod
    def create_for_embedding(
        base_url: Optional[str] = None,
        **kwargs
    ) -> OpenAI:
        """
        Create OpenAI client for embedding operations.

        High throughput disabled by default (embeddings are already batched).
        """
        return OpenAIClientFactory.create(
            base_url=base_url,
            high_throughput=kwargs.pop("high_throughput", False),
            **kwargs
        )
