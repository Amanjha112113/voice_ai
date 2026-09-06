"""Deepgram Aura Streaming TTS Adapter for EchoDrive.

Streams ultra-realistic voice audio using Deepgram Aura neural models (sub-150ms TTFA).
"""

import asyncio
from typing import AsyncGenerator, Optional
import aiohttp
import logging

from .base import TTSProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class DeepgramTTSProvider(TTSProvider):
    """Deepgram Aura streaming Text-to-Speech synthesis adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "aura-asteria-en",  # Professional, natural female voice
    ) -> None:
        self.api_key = api_key or getattr(settings, "DEEPGRAM_API_KEY", None) or ""
        self.model = model
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=5.0, connect=1.5)
            connector = aiohttp.TCPConnector(limit=20, keepalive_timeout=30.0)
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self._session

    async def synthesize_stream(
        self,
        text: str,
        generation_id: str,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> AsyncGenerator[bytes, None]:
        if not text.strip():
            return

        if not self.api_key or self.api_key == "dummy-key":
            num_frames = max(2, len(text.split()) * 2)
            frame_bytes = b"\x00\x00" * 320
            for _ in range(num_frames):
                yield frame_bytes
                await asyncio.sleep(0.02)
            return

        url = f"https://api.deepgram.com/v1/speak?model={self.model}&encoding=linear16&sample_rate=16000"
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    async for chunk in response.content.iter_chunked(640):
                        yield chunk
                else:
                    err_text = await response.text()
                    logger.warning(f"Deepgram TTS notice ({response.status}): {err_text[:120]}")
                    num_frames = max(2, len(text.split()) * 2)
                    for _ in range(num_frames):
                        yield b"\x00\x00" * 320
                        await asyncio.sleep(0.02)
        except Exception as e:
            logger.warning(f"Deepgram TTS streaming exception: {e}")
            num_frames = max(2, len(text.split()) * 2)
            for _ in range(num_frames):
                yield b"\x00\x00" * 320
                await asyncio.sleep(0.02)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
