"""Deepgram WebSocket Streaming ASR Adapter for EchoDrive.

Streams raw 16kHz PCM audio frames and yields interim/final transcription results.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional, Tuple
import aiohttp
import logging

from .base import ASRProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class DeepgramASRProvider(ASRProvider):
    """Deepgram real-time streaming Speech-to-Text adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        sample_rate: int = 16000,
        language: str = "en-IN",
    ) -> None:
        self.api_key = api_key or settings.DEEPGRAM_API_KEY or "dummy-key"
        self.sample_rate = sample_rate
        self.language = language

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._queue: asyncio.Queue[Tuple[str, bool]] = asyncio.Queue()
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self) -> None:
        """Establish WebSocket connection to Deepgram Nova-2."""
        if not self.api_key or self.api_key == "dummy-key":
            logger.warning("Deepgram API Key not set; running in offline mode")
            self._connected = True
            return

        self._session = aiohttp.ClientSession()
        url = (
            f"wss://api.deepgram.com/v1/listen?"
            f"model=nova-2&language={self.language}&encoding=linear16"
            f"&sample_rate={self.sample_rate}&channels=1&interim_results=true&endpointing=300"
        )
        headers = {"Authorization": f"Token {self.api_key}"}

        try:
            self._ws = await self._session.ws_connect(url, headers=headers)
            self._connected = True
            self._receive_task = asyncio.create_task(self._listen_loop())
            logger.info("Connected to Deepgram WebSocket ASR")
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram ASR: {e}", exc_info=True)
            self._connected = False

    async def send_audio_chunk(self, pcm_bytes: bytes) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.send_bytes(pcm_bytes)

    async def _listen_loop(self) -> None:
        """Background loop reading transcripts from Deepgram."""
        if not self._ws:
            return
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")
                        is_final = data.get("is_final", False)
                        if transcript:
                            await self._queue.put((transcript, is_final))
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Deepgram listen loop error: {e}", exc_info=True)

    async def receive_transcripts(self) -> AsyncGenerator[Tuple[str, bool], None]:
        while self._connected:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield item
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)

    async def close(self) -> None:
        self._connected = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Closed Deepgram ASR connection")
