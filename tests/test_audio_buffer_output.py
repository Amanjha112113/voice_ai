"""Unit tests for BoundedAudioBuffer and AudioOutputController."""

import pytest
import asyncio
from backend.app.voice.audio_buffer import BoundedAudioBuffer, DEFAULT_FRAME_SIZE
from backend.app.voice.generation import GenerationController
from backend.app.voice.audio_output import AudioOutputController
from backend.app.voice.events import AsyncEventBus


@pytest.mark.asyncio
async def test_audio_buffer_chunking():
    buf = BoundedAudioBuffer(max_frames=10, frame_size=640)
    # Push 1280 bytes = exactly 2 frames of 640 bytes
    raw_data = b"\x00" * 1280
    frames_count = await buf.push_raw_bytes(raw_data, generation_id="gen_1")
    assert frames_count == 2
    assert buf.qsize == 2

    f1 = await buf.get_frame(timeout=0.1)
    assert f1 is not None
    assert len(f1.data) == 640
    assert f1.sequence_number == 0

    f2 = await buf.get_frame(timeout=0.1)
    assert f2 is not None
    assert len(f2.data) == 640
    assert f2.sequence_number == 1


@pytest.mark.asyncio
async def test_audio_buffer_flush():
    buf = BoundedAudioBuffer(max_frames=10, frame_size=640)
    await buf.push_raw_bytes(b"\x00" * 1920) # 3 frames
    assert buf.qsize == 3

    flushed = await buf.flush()
    assert flushed == 3
    assert buf.is_empty()


@pytest.mark.asyncio
async def test_audio_buffer_backpressure_drop():
    # Max size = 2
    buf = BoundedAudioBuffer(max_frames=2, frame_size=640)
    # Push 4 frames (2560 bytes)
    await buf.push_raw_bytes(b"\x00" * 2560)
    # Buffer should not exceed max_frames
    assert buf.qsize <= 2
