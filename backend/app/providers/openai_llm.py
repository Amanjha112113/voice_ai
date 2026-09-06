"""OpenAI Streaming LLM Adapter for EchoDrive.

Uses AsyncOpenAI with persistent connection pooling and streaming SSE tokens.
"""

from typing import AsyncGenerator, Dict, List, Optional
import httpx
from openai import AsyncOpenAI
import logging

from .base import LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """OpenAI streaming chat completions adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY or "dummy-key"
        self.model = model or settings.OPENAI_MODEL

        # Managed HTTP client with connection reuse & HTTP/2
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=15),
            http2=True,
        )
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            http_client=self._http_client,
        )

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        generation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(messages)

        logger.debug(f"OpenAI LLM: starting stream for gen={generation_id}, model={self.model}")
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=payload_messages,
                stream=True,
                temperature=0.7,
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
        except Exception as e:
            logger.error(f"OpenAI LLM Stream Error: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        await self._http_client.aclose()
