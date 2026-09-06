"""Unit tests for VoiceStateMachine."""

import pytest
import asyncio
from backend.app.voice.state_machine import VoiceStateMachine, VoiceState, InvalidStateTransitionError


@pytest.mark.asyncio
async def test_valid_conversation_transitions():
    sm = VoiceStateMachine(session_id="test_sess")
    assert sm.current_state == VoiceState.IDLE

    # IDLE -> LISTENING
    await sm.transition_to(VoiceState.LISTENING, "User started speaking")
    assert sm.is_listening()

    # LISTENING -> THINKING
    await sm.transition_to(VoiceState.THINKING, "Turn completed")
    assert sm.is_thinking()

    # THINKING -> SPEAKING
    await sm.transition_to(VoiceState.SPEAKING, "Audio playback started")
    assert sm.is_speaking()

    # SPEAKING -> LISTENING
    await sm.transition_to(VoiceState.LISTENING, "Playback complete")
    assert sm.is_listening()


@pytest.mark.asyncio
async def test_interruption_transitions():
    sm = VoiceStateMachine(session_id="test_sess")
    await sm.transition_to(VoiceState.LISTENING)
    await sm.transition_to(VoiceState.THINKING)
    await sm.transition_to(VoiceState.SPEAKING)

    # SPEAKING -> INTERRUPTING
    assert sm.can_transition_to(VoiceState.INTERRUPTING)
    await sm.transition_to(VoiceState.INTERRUPTING, "User barge-in")
    assert sm.is_interrupting()

    # INTERRUPTING -> LISTENING
    assert sm.can_transition_to(VoiceState.LISTENING)
    await sm.transition_to(VoiceState.LISTENING, "Ready for new speech")
    assert sm.is_listening()


@pytest.mark.asyncio
async def test_invalid_transitions_rejected():
    sm = VoiceStateMachine(session_id="test_sess")
    assert sm.current_state == VoiceState.IDLE

    # IDLE -> THINKING is invalid
    assert not sm.can_transition_to(VoiceState.THINKING)
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await sm.transition_to(VoiceState.THINKING)
    assert exc_info.value.current_state == VoiceState.IDLE
    assert exc_info.value.target_state == VoiceState.THINKING


@pytest.mark.asyncio
async def test_state_machine_listeners():
    sm = VoiceStateMachine(session_id="test_sess")
    transitions = []

    def on_change(old_state: VoiceState, new_state: VoiceState):
        transitions.append((old_state, new_state))

    sm.add_listener(on_change)
    await sm.transition_to(VoiceState.LISTENING)
    await sm.transition_to(VoiceState.THINKING)

    assert len(transitions) == 2
    assert transitions[0] == (VoiceState.IDLE, VoiceState.LISTENING)
    assert transitions[1] == (VoiceState.LISTENING, VoiceState.THINKING)
