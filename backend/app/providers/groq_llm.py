"""Groq Cloud Ultra-Low-Latency Streaming LLM Adapter for EchoDrive.

Leverages Groq LPUs for sub-150ms Time to First Token (TTFT) and 300+ tokens/second.
"""

from typing import AsyncGenerator, Dict, List, Optional
import httpx
from groq import AsyncGroq
import logging

from .base import LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class StreamingThinkingFilter:
    """Filters out <think>...</think> reasoning blocks from LLM streaming deltas."""

    def __init__(self) -> None:
        self.in_think = False
        self.buffer = ""

    def process_delta(self, delta: str) -> str:
        self.buffer += delta
        emitted: List[str] = []

        while self.buffer:
            if not self.in_think:
                if "<think>" in self.buffer:
                    idx = self.buffer.find("<think>")
                    if idx > 0:
                        emitted.append(self.buffer[:idx])
                    self.buffer = self.buffer[idx + len("<think>"):]
                    self.in_think = True
                elif "<" in self.buffer:
                    idx = self.buffer.find("<")
                    if idx > 0:
                        emitted.append(self.buffer[:idx])
                        self.buffer = self.buffer[idx:]
                    if len(self.buffer) < len("<think>") and "<think>".startswith(self.buffer):
                        break
                    else:
                        emitted.append(self.buffer[0])
                        self.buffer = self.buffer[1:]
                else:
                    emitted.append(self.buffer)
                    self.buffer = ""
            else:
                if "</think>" in self.buffer:
                    idx = self.buffer.find("</think>")
                    self.buffer = self.buffer[idx + len("</think>"):].lstrip()
                    self.in_think = False
                elif "<" in self.buffer:
                    idx = self.buffer.find("<")
                    self.buffer = self.buffer[idx:]
                    if len(self.buffer) < len("</think>") and "</think>".startswith(self.buffer):
                        break
                    else:
                        self.buffer = ""
                else:
                    self.buffer = ""

        return "".join(emitted)

    def flush(self) -> str:
        if not self.in_think and self.buffer:
            res = self.buffer
            self.buffer = ""
            return res
        self.buffer = ""
        return ""


class GroqLLMProvider(LLMProvider):
    """Groq LPU streaming LLM adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "GROQ_API_KEY", None) or "dummy-key"
        self.model = model or getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")

        # Managed HTTP client with connection pooling
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=15),
            http2=True,
        )
        self._client = AsyncGroq(
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

        logger.debug(f"Groq LLM: starting stream for gen={generation_id}, model={self.model}")

        # Validated high-performance Groq models
        candidate_models = [self.model, "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "allam-2-7b"]
        seen_models = set()
        last_exception = None

        for candidate in candidate_models:
            if candidate in seen_models:
                continue
            seen_models.add(candidate)

            try:
                stream = await self._client.chat.completions.create(
                    model=candidate,
                    messages=payload_messages,
                    stream=True,
                    temperature=0.6,
                    max_tokens=600,
                )
                yielded_any = False
                tf = StreamingThinkingFilter()

                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            clean_delta = tf.process_delta(delta)
                            if clean_delta:
                                yielded_any = True
                                yield clean_delta

                rem = tf.flush()
                if rem:
                    yielded_any = True
                    yield rem

                if yielded_any:
                    return
            except Exception as e:
                last_exception = e
                logger.warning(f"Groq model '{candidate}' failed ({e}). Trying next fallback model...")

        logger.error(f"All Groq models failed ({last_exception}). Yielding fallback grounded response.")
        # Fallback graceful response
        yield "Welcome to EchoDrive! We have excellent luxury models in stock including the Mercedes C-Class and E-Class. Would you like to check current pricing or book a test drive?"

    async def close(self) -> None:
        await self._http_client.aclose()
