"""Unit tests for GenerationController and CancellationController."""

import pytest
import asyncio
from backend.app.voice.generation import GenerationController
from backend.app.voice.state_machine import VoiceStateMachine, VoiceState
from backend.app.voice.audio_output import AudioOutputController
from backend.app.voice.audio_buffer import BoundedAudioBuffer
from backend.app.voice.chunker import StreamingChunker
from backend.app.voice.cancellation import CancellationController
from backend.app.voice.events import AsyncEventBus


def test_generation_controller_invalidation():
    gc = GenerationController(session_id="test_sess")
    gen_1 = gc.active_generation_id
    assert gc.is_valid(gen_1)

    old_gen, gen_2 = gc.invalidate()
    assert old_gen == gen_1
    assert gen_2 != gen_1
    assert not gc.is_valid(gen_1)
    assert gc.is_valid(gen_2)


@pytest.mark.asyncio
async def test_audio_output_rejects_stale_generation_audio():
    gc = GenerationController(session_id="test_sess")
    eb = AsyncEventBus()
    played_chunks = []

    async def mock_sink(data: bytes):
        played_chunks.append(data)

    output = AudioOutputController(
        session_id="test_sess",
        generation_controller=gc,
        event_bus=eb,
        playback_sink=mock_sink,
    )

    gen_1 = gc.active_generation_id

    # Enqueue chunk for gen_1 (valid)
    res_1 = await output.play_chunk_direct(b"audio_chunk_1", generation_id=gen_1, chunk_index=1)
    assert res_1 is True
    assert len(played_chunks) == 1
    assert output.stale_chunks_rejected == 0

    # Invalidate gen_1 -> gen_2
    gc.invalidate()

    # Attempt to play old chunk for gen_1 (obsolete)
    res_stale = await output.play_chunk_direct(b"audio_chunk_2_stale", generation_id=gen_1, chunk_index=2)
    assert res_stale is False
    assert len(played_chunks) == 1  # Not sent to playback sink!
    assert output.stale_chunks_rejected == 1


@pytest.mark.asyncio
async def test_cancellation_controller_idempotent():
    session_id = "test_sess"
    sm = VoiceStateMachine(session_id)
    gc = GenerationController(session_id)
    eb = AsyncEventBus()
    buf = BoundedAudioBuffer()
    chunker = StreamingChunker()
    output = AudioOutputController(session_id, gc, eb)

    cancellation = CancellationController(
        session_id=session_id,
        state_machine=sm,
        generation_controller=gc,
        audio_output=output,
        audio_buffer=buf,
        chunker=chunker,
        event_bus=eb,
    )

    # Set initial state to SPEAKING
    await sm.transition_to(VoiceState.LISTENING)
    await sm.transition_to(VoiceState.THINKING)
    await sm.transition_to(VoiceState.SPEAKING)

    # Create dummy tasks to simulate active LLM and TTS
    async def dummy_loop():
        await asyncio.sleep(10)

    llm_task = asyncio.create_task(dummy_loop())
    tts_task = asyncio.create_task(dummy_loop())
    cancellation.register_llm_task(llm_task)
    cancellation.register_tts_task(tts_task)

    # First interruption
    stop_latency_ms = await cancellation.interrupt(reason="user_barge_in")
    await asyncio.sleep(0)
    assert stop_latency_ms >= 0.0
    assert llm_task.cancelling() or llm_task.cancelled() or llm_task.done()
    assert tts_task.cancelling() or tts_task.cancelled() or tts_task.done()
    assert sm.current_state == VoiceState.LISTENING

    # Second interruption (idempotent call while already in LISTENING)
    stop_latency_2 = await cancellation.interrupt(reason="repeated_interruption")
    assert stop_latency_2 >= 0.0
    assert sm.current_state == VoiceState.LISTENING
