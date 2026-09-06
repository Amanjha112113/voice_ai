"""Bounded Audio Buffer for Realtime Voice Streams.

Responsible for:
- Bounded audio frame queues with backpressure
- Frame ordering and chunking (16kHz, 16-bit mono PCM = 640 bytes / 20ms)
- Buffer flushing after interruption
- Preventing stale frames from reaching downstream processing
"""

import asyncio
from dataclasses import dataclass
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)

BYTES_PER_SAMPLE = 2
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FRAME_MS = 20
DEFAULT_FRAME_SIZE = (DEFAULT_SAMPLE_RATE * DEFAULT_FRAME_MS // 1000) * BYTES_PER_SAMPLE  # 640 bytes


@dataclass
class AudioFrame:
    """Represents a single PCM audio frame."""
    data: bytes
    timestamp_ns: int
    generation_id: Optional[str] = None
    sequence_number: int = 0
    sample_rate: int = DEFAULT_SAMPLE_RATE


class BoundedAudioBuffer:
    """Async bounded audio buffer supporting backpressure and instant flushing."""

    def __init__(self, max_frames: int = 100, frame_size: int = DEFAULT_FRAME_SIZE) -> None:
        self.max_frames = max_frames
        self.frame_size = frame_size
        self._queue: asyncio.Queue[AudioFrame] = asyncio.Queue(maxsize=max_frames)
        self._accum_buffer: bytearray = bytearray()
        self._seq: int = 0
        self._lock = asyncio.Lock()

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    def is_empty(self) -> bool:
        return self._queue.empty()

    async def push_raw_bytes(self, raw_audio: bytes, generation_id: Optional[str] = None) -> int:
        """Push raw audio stream bytes, slice into exact frame chunks, and enqueue.
        
        Returns:
            Number of frames produced and enqueued.
        """
        async with self._lock:
            self._accum_buffer.extend(raw_audio)
            frames_enqueued = 0

            while len(self._accum_buffer) >= self.frame_size:
                frame_data = bytes(self._accum_buffer[:self.frame_size])
                del self._accum_buffer[:self.frame_size]

                frame = AudioFrame(
                    data=frame_data,
                    timestamp_ns=time.perf_counter_ns(),
                    generation_id=generation_id,
                    sequence_number=self._seq,
                )
                self._seq += 1

                # If queue is full, drop the oldest frame to preserve low latency
                if self._queue.full():
                    try:
                        dropped = self._queue.get_nowait()
                        self._queue.task_done()
                        logger.debug(f"Audio buffer backpressure: dropped oldest frame seq={dropped.sequence_number}")
                    except asyncio.QueueEmpty:
                        pass

                try:
                    self._queue.put_nowait(frame)
                    frames_enqueued += 1
                except asyncio.QueueFull:
                    logger.warning("Audio buffer still full after drop; frame discarded")

            return frames_enqueued

    async def get_frame(self, timeout: Optional[float] = None) -> Optional[AudioFrame]:
        """Fetch the next audio frame from the buffer."""
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def task_done(self) -> None:
        self._queue.task_done()

    async def flush(self) -> int:
        """Immediately clear the queue and raw accumulator buffer on barge-in.
        
        Returns:
            Count of flushed frames.
        """
        async with self._lock:
            self._accum_buffer.clear()
            dropped_count = 0
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                    dropped_count += 1
                except asyncio.QueueEmpty:
                    break
            logger.info(f"Audio buffer flushed: {dropped_count} frames discarded")
            return dropped_count
