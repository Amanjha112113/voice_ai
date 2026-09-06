"""Deterministic Mock Providers for EchoDrive.

Provides calibrated, reproducible streaming behavior for CI tests,
latency benchmarking, and barge-in testing without external network dependencies.
"""

import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Tuple
import logging

from .base import ASRProvider, LLMProvider, TTSProvider

logger = logging.getLogger(__name__)


class MockASRProvider(ASRProvider):
    """Calibrated streaming ASR mock."""

    def __init__(self, latency_ms: float = 80.0) -> None:
        self.latency_ms = latency_ms
        self._connected = False
        self._transcript_queue: asyncio.Queue[Tuple[str, bool]] = asyncio.Queue()

    async def connect(self) -> None:
        self._connected = True

    async def send_audio_chunk(self, pcm_bytes: bytes) -> None:
        pass

    def inject_transcript(self, text: str, is_final: bool = True) -> None:
        self._transcript_queue.put_nowait((text, is_final))

    async def receive_transcripts(self) -> AsyncGenerator[Tuple[str, bool], None]:
        while self._connected:
            try:
                item = await asyncio.wait_for(self._transcript_queue.get(), timeout=0.1)
                yield item
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)

    async def close(self) -> None:
        self._connected = False


class MockLLMProvider(LLMProvider):
    """Calibrated streaming LLM mock emitting tokens with realistic TTFT and inter-token spacing."""

    def __init__(
        self,
        ttft_ms: float = 120.0,
        token_interval_ms: float = 15.0,
        fixed_response: str = "Hello! Welcome to EchoDrive. I can help you find your ideal car.",
    ) -> None:
        self.ttft_ms = ttft_ms
        self.token_interval_ms = token_interval_ms
        self.fixed_response = fixed_response

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        generation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        # Simulate Time to First Token (TTFT)
        await asyncio.sleep(self.ttft_ms / 1000.0)

        # Split response into word tokens
        words = self.fixed_response.split(" ")
        for i, word in enumerate(words):
            delta = word if i == 0 else f" {word}"
            yield delta
            await asyncio.sleep(self.token_interval_ms / 1000.0)


class MockTTSProvider(TTSProvider):
    """Calibrated streaming TTS mock emitting PCM frames with realistic first-audio latency."""

    def __init__(
        self,
        first_audio_ms: float = 70.0,
        chunk_interval_ms: float = 20.0,
        frame_bytes_count: int = 640,
    ) -> None:
        self.first_audio_ms = first_audio_ms
        self.chunk_interval_ms = chunk_interval_ms
        self.frame_bytes_count = frame_bytes_count

    async def synthesize_stream(
        self,
        text: str,
        generation_id: str,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> AsyncGenerator[bytes, None]:
        # Simulate TTS first-chunk latency
        await asyncio.sleep(self.first_audio_ms / 1000.0)

        # Generate simulated 16kHz 16-bit PCM frames based on word count
        num_frames = max(3, len(text.split()) * 3)
        dummy_pcm = b"\x00\x01" * (self.frame_bytes_count // 2)

        for _ in range(num_frames):
            yield dummy_pcm
            await asyncio.sleep(self.chunk_interval_ms / 1000.0)
