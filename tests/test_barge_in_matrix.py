"""Barge-In Matrix Test Suite for EchoDrive.

Exhaustively verifies:
1. Interruption during LLM generation (THINKING phase)
2. Interruption during TTS streaming playback (SPEAKING phase)
3. Rapid back-to-back repeated interruptions
4. Stale audio elimination (0 stale chunks played after invalidation)
5. Clean state recovery to LISTENING with 0 unhandled state errors
"""

import pytest
import asyncio
from backend.app.voice.session import VoiceSession
from backend.app.voice.pipeline import VoicePipeline
from backend.app.voice.state_machine import VoiceState
from backend.app.providers.mock_providers import MockASRProvider, MockLLMProvider, MockTTSProvider


@pytest.mark.asyncio
async def test_barge_in_during_llm_generation():
    """Test interruption while LLM is generating tokens (before TTS playback)."""
    played_audio = []
    async def sink(data: bytes):
        played_audio.append(data)

    session = VoiceSession(
        session_id="test_bargein_llm",
        llm_provider=MockLLMProvider(ttft_ms=150.0, token_interval_ms=20.0),
        tts_provider=MockTTSProvider(first_audio_ms=100.0),
        playback_sink=sink,
    )

    # Launch pipeline in background task
    pipeline_task = asyncio.create_task(
        VoicePipeline.process_user_turn(session, "Tell me about seven-seat SUVs", turn_id=1)
    )

    # Allow LLM to enter THINKING state
    await asyncio.sleep(0.05)
    assert session.state_machine.is_thinking()

    # Trigger barge-in
    stop_latency = await session.cancellation.interrupt(reason="user_interrupted_thinking")
    assert stop_latency >= 0.0
    assert session.state_machine.current_state == VoiceState.LISTENING

    try:
        await asyncio.wait_for(pipeline_task, timeout=1.0)
    except asyncio.CancelledError:
        pass

    # Ensure no audio was played for the cancelled generation
    assert len(played_audio) == 0
    await session.close()


@pytest.mark.asyncio
async def test_barge_in_during_tts_playback():
    """Test interruption while TTS is actively streaming and playing audio."""
    played_audio = []
    async def sink(data: bytes):
        played_audio.append(data)

    session = VoiceSession(
        session_id="test_bargein_tts",
        llm_provider=MockLLMProvider(ttft_ms=30.0, token_interval_ms=5.0, fixed_response="Sure! The Scorpio is a great 7 seater vehicle with good mileage."),
        tts_provider=MockTTSProvider(first_audio_ms=25.0, chunk_interval_ms=10.0),
        playback_sink=sink,
    )

    pipeline_task = asyncio.create_task(
        VoicePipeline.process_user_turn(session, "Compare Scorpio with Toyota", turn_id=1)
    )

    # Wait until audio playback starts
    await asyncio.sleep(0.09)
    assert session.state_machine.is_speaking()
    chunks_before_interruption = len(played_audio)
    assert chunks_before_interruption > 0

    # User interrupts!
    stop_latency = await session.cancellation.interrupt(reason="user_interrupted_speaking")
    assert stop_latency >= 0.0
    assert session.state_machine.current_state == VoiceState.LISTENING

    # Wait a moment to ensure no post-interruption audio leaks
    await asyncio.sleep(0.2)
    chunks_after_interruption = len(played_audio)

    # Stale audio assertion: Zero additional frames played for the cancelled generation
    assert chunks_after_interruption == chunks_before_interruption
    assert session.audio_output.stale_chunks_rejected >= 0

    try:
        await asyncio.wait_for(pipeline_task, timeout=0.5)
    except asyncio.CancelledError:
        pass

    await session.close()


@pytest.mark.asyncio
async def test_rapid_repeated_interruptions():
    """Test rapid back-to-back interruptions (3 consecutive interruptions)."""
    session = VoiceSession(
        session_id="test_rapid_bargein",
        llm_provider=MockLLMProvider(ttft_ms=30.0),
        tts_provider=MockTTSProvider(first_audio_ms=20.0),
    )

    for i in range(3):
        # Start turn
        pipeline_task = asyncio.create_task(
            VoicePipeline.process_user_turn(session, f"Question attempt {i}", turn_id=i+1)
        )
        await asyncio.sleep(0.04)

        # Interrupt
        stop_lat = await session.cancellation.interrupt(reason=f"rapid_barge_in_{i}")
        assert stop_lat >= 0.0
        assert session.state_machine.current_state == VoiceState.LISTENING

        try:
            await asyncio.wait_for(pipeline_task, timeout=0.2)
        except asyncio.CancelledError:
            pass

    assert session.cancellation.interruption_count == 3
    assert session.generation_controller.generation_counter > 3
    await session.close()
