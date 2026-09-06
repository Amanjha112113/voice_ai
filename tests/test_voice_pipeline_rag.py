"""Tests for VoicePipeline Partial RAG & MCP Knowledge Retrieval Integration."""

import pytest
import asyncio
from backend.app.voice.session import VoiceSession
from backend.app.voice.pipeline import VoicePipeline
from backend.app.voice.state_machine import VoiceState
from backend.app.providers.mock_providers import MockASRProvider, MockLLMProvider, MockTTSProvider


@pytest.mark.asyncio
async def test_voice_pipeline_processes_turn_with_partial_rag():
    asr = MockASRProvider()
    llm = MockLLMProvider(fixed_response="We have a 7-day return policy with full refund. Would you like to check our sedans?")
    tts = MockTTSProvider(first_audio_ms=10.0)

    session = VoiceSession(
        session_id="test_rag_session",
        agora_channel="test_channel",
        asr_provider=asr,
        llm_provider=llm,
        tts_provider=tts,
    )

    played_audio = []
    async def sink(data: bytes):
        played_audio.append(data)

    session.audio_output.playback_sink = sink

    # Process turn with a warranty / policy query
    telemetry = await VoicePipeline.process_user_turn(
        session=session,
        user_text="What is your return policy and warranty on the Mercedes C-Class?",
        turn_id=1,
    )

    assert telemetry.turn_id == 1
    assert telemetry.ttfa_ms is not None
    assert telemetry.ttfa_ms >= 0.0
    assert len(played_audio) > 0
    assert session.state_machine.current_state == VoiceState.LISTENING

    # Verify conversation memory recorded
    assert len(session.conversation_history) == 2
    assert session.conversation_history[0]["role"] == "user"
    assert "return policy" in session.conversation_history[0]["content"]
    assert session.conversation_history[1]["role"] == "assistant"
