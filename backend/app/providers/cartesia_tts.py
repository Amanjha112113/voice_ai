"""Cartesia Streaming TTS Adapter for EchoDrive.

Streams ultra-low-latency 16kHz PCM audio bytes for human conversational prosody.
"""

import asyncio
from typing import AsyncGenerator, Optional
import aiohttp
import json
import logging

from .base import TTSProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class CartesiaTTSProvider(TTSProvider):
    """Cartesia streaming Text-to-Speech synthesis adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> None:
        self.api_key = api_key or settings.CARTESIA_API_KEY or "dummy-key"
        self.voice_id = voice_id or settings.CARTESIA_VOICE_ID
        self.sample_rate = sample_rate

    async def synthesize_stream(
        self,
        text: str,
        generation_id: str,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> AsyncGenerator[bytes, None]:
        if not text.strip():
            return

        logger.debug(f"Cartesia TTS: synthesizing chunk #{chunk_index} for gen={generation_id}: '{text}'")

        if not self.api_key or self.api_key == "dummy-key":
            # Fallback simulated audio for testing without live API keys
            num_frames = max(2, len(text.split()) * 2)
            frame_bytes = b"\x00\x00" * 320 # 640 bytes per 20ms
            for _ in range(num_frames):
                yield frame_bytes
                await asyncio.sleep(0.02)
            return

        # Real streaming call to Cartesia TTS API
        url = "https://api.cartesia.ai/tts/bytes"
        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json",
        }
        payload = {
            "model_id": "sonic-english",
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice_id},
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self.sample_rate,
            },
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        async for chunk in response.content.iter_chunked(640):
                            yield chunk
                    else:
                        err_text = await response.text()
                        logger.error(f"Cartesia TTS API Error {response.status}: {err_text}")
            except Exception as e:
                logger.error(f"Cartesia synthesis error: {e}", exc_info=True)
