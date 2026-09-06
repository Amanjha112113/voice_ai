"""ElevenLabs Streaming TTS Adapter for EchoDrive.

Streams ultra-realistic voice audio using ElevenLabs low-latency Flash v2.5 / Turbo models.
"""

import asyncio
from typing import AsyncGenerator, Optional
import aiohttp
import logging

from .base import TTSProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs streaming Text-to-Speech synthesis adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_flash_v2_5",       # Ultra-low latency model
    ) -> None:
        self.api_key = api_key or getattr(settings, "ELEVENLABS_API_KEY", None) or ""
        self.voice_id = voice_id or getattr(settings, "ELEVENLABS_VOICE_ID", None) or ""
        self.model_id = model_id
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=3.0, connect=1.0)
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

        logger.debug(f"ElevenLabs TTS: synthesizing chunk #{chunk_index} for gen={generation_id}: '{text}'")

        if not self.api_key or self.api_key == "dummy-key" or not self.voice_id:
            # Fallback simulated audio if key/voice not configured
            num_frames = max(2, len(text.split()) * 2)
            frame_bytes = b"\x00\x00" * 320  # 640 bytes per 20ms
            for _ in range(num_frames):
                yield frame_bytes
                await asyncio.sleep(0.02)
            return

        # ElevenLabs Streaming API endpoint (raw 16kHz PCM output)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream?output_format=pcm_16000"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    async for chunk in response.content.iter_chunked(640):
                        yield chunk
                else:
                    err_text = await response.text()
                    logger.warning(f"ElevenLabs TTS API notice ({response.status}): {err_text[:120]}... Falling back to local PCM stream.")
                    num_frames = max(2, len(text.split()) * 2)
                    dummy_frame = b"\x00\x01" * 320 # 640 bytes per 20ms frame
                    for _ in range(num_frames):
                        yield dummy_frame
                        await asyncio.sleep(0.02)
        except Exception as e:
            logger.warning(f"ElevenLabs synthesis notice/timeout: {e}")
            num_frames = max(2, len(text.split()) * 2)
            dummy_frame = b"\x00\x01" * 320
            for _ in range(num_frames):
                yield dummy_frame
                await asyncio.sleep(0.02)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
