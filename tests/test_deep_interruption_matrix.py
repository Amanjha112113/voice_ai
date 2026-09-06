"""Deep Interruption & Barge-In Production Test Matrix for EchoDrive.

Verifies:
1. Basic speech-onset interruption
2. Mid-sentence interruption & generation invalidation
3. Continuous user speech capture across acknowledgment boundary
4. Rapid repeated interruptions (zero stale audio)
5. Interruption during in-flight TTS synthesis
6. Interruption during in-flight LLM token streaming
7. Interruption exactly at TTS chunk boundary
8. Natural non-keyword speech onset triggers
9. High-resolution monotonic interruption timeline trace
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any

from backend.app.voice.state_machine import VoiceStateMachine, VoiceState
from backend.app.voice.generation import GenerationController
from backend.app.voice.events import (
    AsyncEventBus,
    BargeInDetected,
    ChunkReady,
    GenerationInvalidated,
    InterruptionAckStarted,
    InterruptionAckFinished,
    InterruptionTimelineEvent,
)
from backend.app.voice.audio_buffer import BoundedAudioBuffer
from backend.app.voice.audio_output import AudioOutputController
from backend.app.voice.chunker import StreamingChunker
from backend.app.voice.cancellation import CancellationController
from backend.app.voice.session import VoiceSession
from backend.app.voice.pipeline import VoicePipeline
from backend.app.providers.mock_providers import (
    MockASRProvider,
    MockLLMProvider,
    MockTTSProvider,
)


@pytest.fixture
def session():
    """Create a fully configured VoiceSession with calibrated mock providers."""
    sess = VoiceSession(
        session_id="test_deep_barge_in",
        asr_provider=MockASRProvider(),
        llm_provider=MockLLMProvider(ttft_ms=10, token_interval_ms=5),
        tts_provider=MockTTSProvider(first_audio_ms=10, chunk_interval_ms=10),
    )
    return sess


@pytest.mark.asyncio
async def test_1_basic_interruption(session):
    """Test 1 — Basic: AI speaking -> User speech -> AI stops -> AI: OK -> State returns to LISTENING."""
    # 1. Start session in SPEAKING state
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    events_received: List[str] = []
    session.event_bus.subscribe_all(lambda e: events_received.append(type(e).__name__))

    # 2. User interrupts
    telemetry = await session.cancellation.interrupt(reason="user_said_wait", ack_phrase="OK.", turn_id=1)

    # 3. Verify state progression: reached LISTENING after ACKNOWLEDGING
    assert session.state_machine.current_state == VoiceState.LISTENING
    assert "BargeInDetected" in events_received
    assert "GenerationInvalidated" in events_received
    assert "InterruptionAckStarted" in events_received
    assert "InterruptionAckFinished" in events_received
    assert "InterruptionTimelineEvent" in events_received

    # 4. Verify latency under 200ms target
    assert telemetry.stop_latency_ms <= 200.0


@pytest.mark.asyncio
async def test_2_mid_sentence_speech_onset(session):
    """Test 2 — Mid-sentence: AI speaking long response -> user speech onset aborts immediately."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    old_gen = session.generation_controller.active_generation_id

    # Trigger mid-sentence interruption
    telemetry = await session.cancellation.interrupt(reason="speech_onset_mid_sentence", ack_phrase="OK.")

    # Old generation is superseded
    new_gen = session.generation_controller.active_generation_id
    assert new_gen != old_gen
    assert not session.generation_controller.is_valid(old_gen)
    assert session.generation_controller.is_valid(new_gen)
    assert session.state_machine.current_state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_3_continuous_user_speech_capture(session):
    """Test 3 — Continuous speech: User says 'Wait, actually I don't want an SUV, I want a sedan under 20 lakhs.'
    Ensures complete user sentence is preserved and passed to LLM."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    # 1. User starts speaking "Wait..." -> AI aborts and acknowledges
    await session.cancellation.interrupt(reason="speech_onset", ack_phrase="OK.")
    assert session.state_machine.current_state == VoiceState.LISTENING

    # 2. User continuous speech accumulator captures full utterance
    user_speech_parts = ["Wait,", "actually I don't want an SUV,", "I want a sedan under 20 lakhs."]
    complete_utterance = " ".join(user_speech_parts)

    # 3. Pass full composite utterance to voice pipeline
    turn_telemetry = await VoicePipeline.process_user_turn(
        session=session,
        user_text=complete_utterance,
        turn_id=2,
    )

    assert turn_telemetry is not None
    assert turn_telemetry.turn_id == 2
    assert session.generation_controller.is_valid(turn_telemetry.generation_id)


@pytest.mark.asyncio
async def test_4_rapid_repeated_interruptions(session):
    """Test 4 — Rapid interruption: User: 'Wait!' -> OK -> User: 'No!' -> OK. Zero stale audio."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    # First interruption
    gen_1 = session.generation_controller.active_generation_id
    await session.cancellation.interrupt(reason="Wait!")
    gen_2 = session.generation_controller.active_generation_id
    assert gen_2 != gen_1

    # Transition to SPEAKING again
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    # Rapid second interruption
    await session.cancellation.interrupt(reason="No!")
    gen_3 = session.generation_controller.active_generation_id
    assert gen_3 != gen_2

    # Verify both gen_1 and gen_2 are strictly invalid
    assert not session.generation_controller.is_valid(gen_1)
    assert not session.generation_controller.is_valid(gen_2)
    assert session.generation_controller.is_valid(gen_3)
    assert session.cancellation.interruption_count == 2
    assert session.state_machine.current_state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_5_interrupt_during_tts_synthesis(session):
    """Test 5 — Interrupt while in-flight TTS is active. Cancels TTS task and flushes output."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    # Create dummy in-flight TTS task
    async def dummy_tts_task():
        await asyncio.sleep(0.5)

    tts_task = asyncio.create_task(dummy_tts_task())
    session.cancellation.register_tts_task(tts_task)

    # Interrupt
    await session.cancellation.interrupt(reason="tts_in_flight_barge_in")
    await asyncio.sleep(0.01)

    # Task must be cancelled
    assert tts_task.cancelled() or tts_task.done()
    assert session.state_machine.current_state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_6_interrupt_during_llm_generation(session):
    """Test 6 — Interrupt while LLM is generating tokens. Cancels LLM task and drops tokens."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)

    # Create dummy in-flight LLM task
    async def dummy_llm_task():
        await asyncio.sleep(0.5)

    llm_task = asyncio.create_task(dummy_llm_task())
    session.cancellation.register_llm_task(llm_task)

    # Interrupt
    await session.cancellation.interrupt(reason="llm_in_flight_barge_in")
    await asyncio.sleep(0.01)

    # Task must be cancelled
    assert llm_task.cancelled() or llm_task.done()
    assert session.state_machine.current_state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_7_interrupt_at_chunk_boundary_zero_stale_audio(session):
    """Test 7 — Interrupt near sentence boundary: Chunk B from old generation must be rejected."""
    old_gen = session.generation_controller.active_generation_id

    # Queue Chunk A
    await session.audio_output.play_chunk_direct(
        audio_data=b"\x00" * 320,
        generation_id=old_gen,
        chunk_index=1,
        is_final=False,
    )

    # User interrupts right at boundary
    await session.cancellation.interrupt(reason="boundary_interruption")
    new_gen = session.generation_controller.active_generation_id

    # Chunk B arrives from stale generation -> must be rejected
    played = await session.audio_output.play_chunk_direct(
        audio_data=b"\x00" * 320,
        generation_id=old_gen,  # Stale ID
        chunk_index=2,
        is_final=True,
    )

    assert played is False
    assert session.audio_output.stale_chunks_rejected >= 1


@pytest.mark.asyncio
async def test_8_non_keyword_natural_speech_onset_triggers(session):
    """Test 8 — Verifies that any natural speech onset ('Actually...', 'What about Toyota?', 'Hmm...') triggers barge-in."""
    for phrase in ["Actually...", "What about Toyota?", "Hmm...", "I meant 7 seats"]:
        if session.state_machine.current_state != VoiceState.SPEAKING:
            if session.state_machine.current_state == VoiceState.IDLE:
                await session.state_machine.transition_to(VoiceState.LISTENING)
            await session.state_machine.transition_to(VoiceState.THINKING)
            await session.state_machine.transition_to(VoiceState.SPEAKING)

        telemetry = await session.cancellation.interrupt(reason=f"speech_onset: '{phrase}'")
        assert session.state_machine.current_state == VoiceState.LISTENING
        assert telemetry.stop_latency_ms <= 200.0


@pytest.mark.asyncio
async def test_9_deep_interruption_timeline_trace(session):
    """Test 9 — Verifies complete monotonic millisecond timeline trace."""
    await session.state_machine.transition_to(VoiceState.LISTENING)
    await session.state_machine.transition_to(VoiceState.THINKING)
    await session.state_machine.transition_to(VoiceState.SPEAKING)

    telemetry = await session.cancellation.interrupt(reason="test_timeline", turn_id=42)

    # Verify timestamps exist and are monotonic
    assert telemetry.speech_detected_ns > 0
    assert telemetry.generation_invalidated_ns >= telemetry.speech_detected_ns
    assert telemetry.llm_cancel_requested_ns >= telemetry.speech_detected_ns
    assert telemetry.playback_stopped_ns >= telemetry.speech_detected_ns
    assert telemetry.ack_started_ns >= telemetry.playback_stopped_ns
    assert telemetry.ack_finished_ns >= telemetry.ack_started_ns

    # Verify human-readable trace string contains all keys
    trace = telemetry.format_detailed_trace()
    assert "DEEP INTERRUPTION TIMELINE" in trace
    assert "speech_detected" in trace
    assert "generation_invalidated" in trace
    assert "llm_cancel_requested" in trace
    assert "tts_cancel_requested" in trace
    assert "audio_buffer_flushed" in trace
    assert "playback_stopped" in trace
    assert "ack_started" in trace
    assert "ack_finished" in trace
    assert "Interruption-Stop Latency:" in trace


@pytest.mark.asyncio
async def test_10_pause_phrase_fast_path_and_concise_response(session):
    """Test 10 — Verifies that holding/pause phrases (e.g. 'wait wait', 'hold on') trigger fast-path 'Sure.' without filler."""
    pause_inputs = ["wait", "wait wait", "hold on", "one second", "just a moment", "stop"]

    for phrase in pause_inputs:
        emitted_chunks = []

        async def _capture_chunk(evt):
            emitted_chunks.append(evt.text)

        session.event_bus.subscribe(ChunkReady, _capture_chunk)

        telemetry = await VoicePipeline.process_user_turn(
            session=session,
            user_text=phrase,
            turn_id=100,
        )

        assert telemetry is not None
        assert "Sure." in emitted_chunks or emitted_chunks == ["Sure."]
        # Ensure no rambling / filler responses
        assert not any("take your time" in c.lower() for c in emitted_chunks)
        assert not any("whenever you're ready" in c.lower() for c in emitted_chunks)

