"""Explicit Voice State Machine for EchoDrive.

Eliminates scattered booleans (is_speaking, is_processing, is_interrupted)
in favor of a formal, observable state machine.
"""

from enum import Enum, auto
import logging
from typing import Callable, Dict, List, Optional, Set
import asyncio

logger = logging.getLogger(__name__)


class VoiceState(str, Enum):
    """Authoritative states of a realtime voice session."""
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTING = "INTERRUPTING"
    ACKNOWLEDGING = "ACKNOWLEDGING"
    ERROR = "ERROR"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, current_state: VoiceState, target_state: VoiceState, reason: str = ""):
        message = f"Invalid state transition: {current_state} -> {target_state}. {reason}".strip()
        super().__init__(message)
        self.current_state = current_state
        self.target_state = target_state


class VoiceStateMachine:
    """Explicit, thread-safe state machine governing session voice lifecycle."""

    # Explicit transition matrix: current_state -> allowed next states
    VALID_TRANSITIONS: Dict[VoiceState, Set[VoiceState]] = {
        VoiceState.IDLE: {VoiceState.LISTENING, VoiceState.SPEAKING, VoiceState.ERROR},
        VoiceState.LISTENING: {VoiceState.THINKING, VoiceState.LISTENING, VoiceState.INTERRUPTING, VoiceState.ERROR, VoiceState.IDLE},
        VoiceState.THINKING: {VoiceState.SPEAKING, VoiceState.INTERRUPTING, VoiceState.ERROR, VoiceState.IDLE},
        VoiceState.SPEAKING: {VoiceState.LISTENING, VoiceState.INTERRUPTING, VoiceState.ERROR, VoiceState.IDLE},
        VoiceState.INTERRUPTING: {VoiceState.ACKNOWLEDGING, VoiceState.LISTENING, VoiceState.ERROR, VoiceState.IDLE},
        VoiceState.ACKNOWLEDGING: {VoiceState.LISTENING, VoiceState.INTERRUPTING, VoiceState.THINKING, VoiceState.ERROR, VoiceState.IDLE},
        VoiceState.ERROR: {VoiceState.LISTENING, VoiceState.IDLE, VoiceState.ERROR},
    }

    def __init__(self, session_id: str, initial_state: VoiceState = VoiceState.IDLE) -> None:
        self.session_id = session_id
        self._current_state: VoiceState = initial_state
        self._listeners: List[Callable[[VoiceState, VoiceState], None]] = []
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> VoiceState:
        return self._current_state

    def is_listening(self) -> bool:
        return self._current_state == VoiceState.LISTENING

    def is_speaking(self) -> bool:
        return self._current_state == VoiceState.SPEAKING

    def is_thinking(self) -> bool:
        return self._current_state == VoiceState.THINKING

    def is_interrupting(self) -> bool:
        return self._current_state == VoiceState.INTERRUPTING

    def is_acknowledging(self) -> bool:
        return self._current_state == VoiceState.ACKNOWLEDGING

    def can_transition_to(self, target_state: VoiceState) -> bool:
        """Check if transition to target_state is permitted from current state."""
        return target_state in self.VALID_TRANSITIONS.get(self._current_state, set())

    async def transition_to(self, target_state: VoiceState, reason: str = "") -> VoiceState:
        """Atomically perform a state transition with validation."""
        async with self._lock:
            if not self.can_transition_to(target_state):
                err = InvalidStateTransitionError(self._current_state, target_state, reason)
                logger.warning(f"[{self.session_id}] {err}")
                raise err

            old_state = self._current_state
            self._current_state = target_state
            logger.info(f"[{self.session_id}] State transition: {old_state} -> {target_state} ({reason})")

            for listener in self._listeners:
                try:
                    listener(old_state, target_state)
                except Exception as e:
                    logger.error(f"[{self.session_id}] Error in state transition listener: {e}", exc_info=True)

            return self._current_state

    def add_listener(self, listener: Callable[[VoiceState, VoiceState], None]) -> None:
        """Register a callback for state transitions."""
        self._listeners.append(listener)
