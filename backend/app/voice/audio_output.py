"""Audio Output Controller for EchoDrive.

The explicit playback boundary sitting between TTS and Agora.
Owns:
- Audio playback to RTC / speaker
- Generation validation & stale chunk rejection (eliminating ghost audio)
- Playback cancellation & output buffer flushing
- Precise playback timestamps for TTFA and interruption stop telemetry
"""

import asyncio
import time
from typing import Callable, Coroutine, Optional, Any
import logging

from .generation import GenerationController
from .events import AsyncEventBus, AudioPlayed, PlaybackStopped

logger = logging.getLogger(__name__)


class AudioOutputController:
    """Controls outgoing synthesized audio rendering to Agora RTC channel."""

    def __init__(
        self,
        session_id: str,
        generation_controller: GenerationController,
        event_bus: AsyncEventBus,
        playback_sink: Optional[Callable[[bytes], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self.session_id = session_id
        self.generation_controller = generation_controller
        self.event_bus = event_bus
        self.playback_sink = playback_sink

        self._active_playback_task: Optional[asyncio.Task] = None
        self._output_queue: asyncio.Queue[tuple[bytes, str, int, bool]] = asyncio.Queue(maxsize=100)
        self._is_playing: bool = False
        self._has_played_first_chunk_for_gen: dict[str, bool] = {}
        self._first_audio_ts: Optional[int] = None
        self._lock = asyncio.Lock()
        self._stale_chunks_rejected: int = 0
        self._chunks_played: int = 0

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def stale_chunks_rejected(self) -> int:
        return self._stale_chunks_rejected

    @property
    def chunks_played(self) -> int:
        return self._chunks_played

    @property
    def first_audio_ts(self) -> Optional[int]:
        return self._first_audio_ts

    async def enqueue_chunk(
        self,
        audio_data: bytes,
        generation_id: str,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> bool:
        """Enqueue an audio chunk for playback after checking generation validity.
        
        Returns:
            True if chunk was enqueued, False if rejected as stale.
        """
        # Stale audio filter check:
        if not self.generation_controller.is_valid(generation_id):
            self._stale_chunks_rejected += 1
            logger.info(
                f"[{self.session_id}] STALE AUDIO REJECTED: Chunk {chunk_index} for obsolete gen={generation_id} "
                f"(active={self.generation_controller.active_generation_id})"
            )
            return False

        try:
            self._output_queue.put_nowait((audio_data, generation_id, chunk_index, is_final))
            return True
        except asyncio.QueueFull:
            logger.warning(f"[{self.session_id}] Output queue full; dropped audio chunk {chunk_index}")
            return False

    async def play_chunk_direct(
        self,
        audio_data: bytes,
        generation_id: str,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> bool:
        """Directly validate and play an audio chunk with generation gating."""
        if not self.generation_controller.is_valid(generation_id):
            self._stale_chunks_rejected += 1
            logger.info(
                f"[{self.session_id}] STALE AUDIO REJECTED (direct): Chunk {chunk_index} for obsolete gen={generation_id} "
                f"(active={self.generation_controller.active_generation_id})"
            )
            return False

        now_ns = time.perf_counter_ns()
        is_first = not self._has_played_first_chunk_for_gen.get(generation_id, False)
        if is_first:
            self._has_played_first_chunk_for_gen[generation_id] = True
            self._first_audio_ts = now_ns
            logger.info(f"[{self.session_id}] FIRST AUDIO PLAYED for gen={generation_id} at {now_ns} ns")

        self._is_playing = True
        self._chunks_played += 1

        # Emit AudioPlayed event
        await self.event_bus.emit(
            AudioPlayed(
                session_id=self.session_id,
                generation_id=generation_id,
                is_first_audio=is_first,
                timestamp_ns=now_ns,
            )
        )

        # Send to RTC playback sink if registered
        if self.playback_sink:
            try:
                await self.playback_sink(audio_data)
            except Exception as e:
                logger.error(f"[{self.session_id}] Playback sink error: {e}", exc_info=True)

        if is_final:
            self._is_playing = False

        return True

    async def stop_playback(self, barge_in_ts_ns: Optional[int] = None) -> float:
        """Immediately stop playback, cancel in-flight playback task, and flush buffer.
        
        Returns:
            interruption stop latency in milliseconds.
        """
        async with self._lock:
            self._is_playing = False
            
            # Cancel active playback task if running
            if self._active_playback_task and not self._active_playback_task.done():
                self._active_playback_task.cancel()
                self._active_playback_task = None

            # Flush output queue
            flushed_count = 0
            while not self._output_queue.empty():
                try:
                    self._output_queue.get_nowait()
                    self._output_queue.task_done()
                    flushed_count += 1
                except asyncio.QueueEmpty:
                    break

            now_ns = time.perf_counter_ns()
            stop_latency_ms = 0.0
            if barge_in_ts_ns is not None:
                stop_latency_ms = (now_ns - barge_in_ts_ns) / 1_000_000.0

            logger.info(
                f"[{self.session_id}] Playback stopped & flushed ({flushed_count} chunks discarded). "
                f"Stop latency: {stop_latency_ms:.2f} ms"
            )

            await self.event_bus.emit(
                PlaybackStopped(
                    session_id=self.session_id,
                    generation_id=self.generation_controller.active_generation_id,
                    stop_latency_ms=stop_latency_ms,
                    timestamp_ns=now_ns,
                )
            )

            return stop_latency_ms
