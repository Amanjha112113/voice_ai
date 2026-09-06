"""Typed In-Process Event Bus for EchoDrive Voice Runtime.

All events are handled in-process via asyncio. No external message broker is required.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Coroutine, Dict, List, Type, TypeVar
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceEvent:
    """Base class for all internal runtime voice events."""
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)


@dataclass(frozen=True)
class SpeechStarted(VoiceEvent):
    """Fired when VAD detects user voice onset."""
    session_id: str = ""


@dataclass(frozen=True)
class SpeechEnded(VoiceEvent):
    """Fired when VAD detects trailing silence indicating user speech offset."""
    session_id: str = ""
    duration_ms: float = 0.0


@dataclass(frozen=True)
class TranscriptPartial(VoiceEvent):
    """Fired when interim ASR result is received."""
    session_id: str = ""
    text: str = ""
    turn_id: int = 0


@dataclass(frozen=True)
class TranscriptFinal(VoiceEvent):
    """Fired when final user transcript for a turn is locked."""
    session_id: str = ""
    text: str = ""
    turn_id: int = 0


@dataclass(frozen=True)
class LLMStarted(VoiceEvent):
    """Fired when prompt is dispatched to LLM."""
    session_id: str = ""
    generation_id: str = ""
    turn_id: int = 0
    prompt: str = ""


@dataclass(frozen=True)
class LLMToken(VoiceEvent):
    """Fired for each streaming token from LLM."""
    session_id: str = ""
    generation_id: str = ""
    delta: str = ""
    is_first_token: bool = False


@dataclass(frozen=True)
class ChunkReady(VoiceEvent):
    """Fired when progressive chunker produces a sentence/clause for TTS."""
    session_id: str = ""
    generation_id: str = ""
    text: str = ""
    chunk_index: int = 0
    is_final: bool = False


@dataclass(frozen=True)
class TTSStarted(VoiceEvent):
    """Fired when a text chunk is sent to TTS engine."""
    session_id: str = ""
    generation_id: str = ""
    chunk_index: int = 0
    text: str = ""


@dataclass(frozen=True)
class AudioChunk(VoiceEvent):
    """Fired when synthesized audio bytes arrive from TTS."""
    session_id: str = ""
    generation_id: str = ""
    chunk_index: int = 0
    data: bytes = b""
    sample_rate: int = 16000
    is_first_chunk: bool = False
    is_final: bool = False


@dataclass(frozen=True)
class AudioPlayed(VoiceEvent):
    """Fired when an audio chunk begins playback via AudioOutputController."""
    session_id: str = ""
    generation_id: str = ""
    is_first_audio: bool = False


@dataclass(frozen=True)
class BargeInDetected(VoiceEvent):
    """Fired immediately when user speaks while agent is generating or speaking."""
    session_id: str = ""
    interrupted_generation_id: str = ""
    interrupted_state: str = ""


@dataclass(frozen=True)
class GenerationInvalidated(VoiceEvent):
    """Fired when an old generation ID is marked stale and discarded."""
    session_id: str = ""
    old_generation_id: str = ""
    new_generation_id: str = ""


@dataclass(frozen=True)
class PlaybackStopped(VoiceEvent):
    """Fired when playback is halted and output buffer is flushed."""
    session_id: str = ""
    generation_id: str = ""
    stop_latency_ms: float = 0.0


@dataclass(frozen=True)
class InterruptionAckStarted(VoiceEvent):
    """Fired when the short interruption acknowledgment ('OK') begins."""
    session_id: str = ""
    generation_id: str = ""
    phrase: str = "OK."


@dataclass(frozen=True)
class InterruptionAckFinished(VoiceEvent):
    """Fired when interruption acknowledgment completes and session returns to LISTENING."""
    session_id: str = ""
    generation_id: str = ""
    duration_ms: float = 0.0


@dataclass(frozen=True)
class InterruptionTimelineEvent(VoiceEvent):
    """Fired with complete millisecond latency trace of interruption lifecycle."""
    session_id: str = ""
    turn_id: int = 0
    speech_detected_ms: float = 0.0
    generation_invalidated_ms: float = 0.0
    llm_cancelled_ms: float = 0.0
    tts_cancelled_ms: float = 0.0
    playback_stopped_ms: float = 0.0
    ack_started_ms: float = 0.0
    ack_finished_ms: float = 0.0
    total_stop_latency_ms: float = 0.0


@dataclass(frozen=True)
class TurnCompleted(VoiceEvent):
    """Fired when a full conversational turn concludes."""
    session_id: str = ""
    turn_id: int = 0
    generation_id: str = ""
    ttfa_ms: float = 0.0
    total_turn_ms: float = 0.0


T = TypeVar("T", bound=VoiceEvent)
EventHandler = Callable[[T], Coroutine[Any, Any, None]]


class AsyncEventBus:
    """Lightweight in-process asyncio event bus."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[VoiceEvent], List[EventHandler[Any]]] = {}
        self._global_handlers: List[EventHandler[VoiceEvent]] = []

    def subscribe(self, event_type: Type[T], handler: EventHandler[T]) -> None:
        """Subscribe an async handler to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler[VoiceEvent]) -> None:
        """Subscribe an async handler to all emitted events."""
        self._global_handlers.append(handler)

    async def emit(self, event: VoiceEvent) -> None:
        """Emit an event to all subscribed handlers concurrently or sequentially."""
        event_type = type(event)
        
        # Specific handlers
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler {handler} for {event_type.__name__}: {e}", exc_info=True)

        # Global handlers
        for global_handler in self._global_handlers:
            try:
                await global_handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler {global_handler} for {event_type.__name__}: {e}", exc_info=True)
