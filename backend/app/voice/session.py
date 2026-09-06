"""Per-Session Container for EchoDrive Voice Runtime.

Encapsulates all state, buffers, controllers, event bus, and task handles
for a single active customer voice session. Guarantees no global mutable state.
"""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Coroutine
import logging

from .state_machine import VoiceStateMachine, VoiceState
from .generation import GenerationController
from .events import AsyncEventBus
from .audio_buffer import BoundedAudioBuffer
from .audio_output import AudioOutputController
from .vad import EnergyVAD
from .turn_detector import TurnDetector
from .chunker import StreamingChunker
from .cancellation import CancellationController
from ..observability.telemetry import TurnTelemetry
from ..observability.metrics import MetricsCollector
from ..providers.base import ASRProvider, LLMProvider, TTSProvider, RTCGateway

logger = logging.getLogger(__name__)


class VoiceSession:
    """Represents a complete, isolated realtime conversational voice session."""

    def __init__(
        self,
        session_id: str,
        customer_id: Optional[str] = None,
        agora_channel: Optional[str] = None,
        agora_token: Optional[str] = None,
        language: str = "en-IN",
        asr_provider: Optional[ASRProvider] = None,
        llm_provider: Optional[LLMProvider] = None,
        tts_provider: Optional[TTSProvider] = None,
        rtc_gateway: Optional[RTCGateway] = None,
        playback_sink: Optional[Callable[[bytes], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self.session_id = session_id
        self.customer_id = customer_id
        self.agora_channel = agora_channel or f"echodrive_{session_id[:8]}"
        self.agora_token = agora_token or ""
        self.language = language
        self.created_at = datetime.utcnow()

        # Providers
        self.asr_provider = asr_provider
        self.llm_provider = llm_provider
        self.tts_provider = tts_provider
        self.rtc_gateway = rtc_gateway

        # In-process Event Bus
        self.event_bus = AsyncEventBus()

        # State Machine
        self.state_machine = VoiceStateMachine(session_id=session_id)

        # Generation Controller
        self.generation_controller = GenerationController(session_id=session_id)

        # Bounded Audio Buffer (Input)
        self.audio_buffer = BoundedAudioBuffer(max_frames=100)

        # Audio Output Controller (Explicit Playback Boundary)
        self.audio_output = AudioOutputController(
            session_id=session_id,
            generation_controller=self.generation_controller,
            event_bus=self.event_bus,
            playback_sink=playback_sink,
        )

        # Progressive Chunker
        self.chunker = StreamingChunker()

        # Cancellation & Barge-in Controller
        self.cancellation = CancellationController(
            session_id=session_id,
            state_machine=self.state_machine,
            generation_controller=self.generation_controller,
            audio_output=self.audio_output,
            audio_buffer=self.audio_buffer,
            chunker=self.chunker,
            event_bus=self.event_bus,
        )

        # VAD
        self.vad = EnergyVAD(
            sample_rate=16000,
            frame_ms=20,
            energy_threshold=0.02,
            on_speech_start=self._on_vad_speech_start,
            on_speech_end=self._on_vad_speech_end,
        )

        # Turn Detector
        self.turn_detector = TurnDetector(
            session_id=session_id,
            on_turn_ready=self._on_turn_ready,
        )

        # Metrics & Telemetry
        self.metrics_collector = MetricsCollector()
        self.current_turn_telemetry: Optional[TurnTelemetry] = None

        # Multi-turn Context Memory
        self.conversation_history: List[Dict[str, str]] = []

        # Wire event bus to dashboard manager for live WebSocket telemetry
        self._setup_event_broadcast()

        # Owned Background Tasks
        self._owned_tasks: List[asyncio.Task] = []
        self._closed: bool = False

    def _setup_event_broadcast(self) -> None:
        """Broadcast events to WebSocket dashboard clients."""
        try:
            from ..api.routes_ws import dashboard_manager

            async def _forward_event(event: Any) -> None:
                event_name = type(event).__name__
                payload = {}
                if hasattr(event, "__dict__"):
                    payload = {k: v for k, v in event.__dict__.items() if k != "data"}
                await dashboard_manager.broadcast_event(event_name, self.session_id, payload)

            self.event_bus.subscribe_all(_forward_event)
        except ImportError:
            # Running in lightweight test environment without FastAPI
            pass

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _on_vad_speech_start(self, timestamp_ns: int) -> None:
        """Called when user starts speaking."""
        self.turn_detector.on_speech_start(timestamp_ns)

        # Trigger barge-in if agent is currently speaking or thinking
        if self.state_machine.is_speaking() or self.state_machine.is_thinking():
            asyncio.create_task(self.cancellation.interrupt(reason="speech_start_during_playback"))
        elif self.state_machine.can_transition_to(VoiceState.LISTENING):
            asyncio.create_task(self.state_machine.transition_to(VoiceState.LISTENING, reason="User speaking"))

    def _on_vad_speech_end(self, timestamp_ns: int, duration_ms: float) -> None:
        """Called when user stops speaking."""
        self.turn_detector.on_speech_end(timestamp_ns, duration_ms)

    def _on_turn_ready(self, text: str, turn_id: int) -> None:
        """Called when user finishes speaking their complete turn."""
        logger.info(f"[{self.session_id}] Turn #{turn_id} ready for generation: '{text}'")

    def register_task(self, task: asyncio.Task) -> None:
        """Track an owned background task for clean shutdown."""
        self._owned_tasks.append(task)

    async def close(self) -> None:
        """Cleanly terminate session, cancel all owned tasks, and release resources."""
        if self._closed:
            return
        self._closed = True
        logger.info(f"[{self.session_id}] Closing voice session...")

        # 1. Trigger cancellation
        await self.cancellation.interrupt(reason="session_closing")

        # 2. Cancel all owned background tasks
        for task in self._owned_tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=0.5)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        self._owned_tasks.clear()

        # 3. Close ASR/RTC providers if present
        if self.asr_provider:
            await self.asr_provider.close()
        if self.rtc_gateway and self.agora_channel:
            await self.rtc_gateway.leave_channel(self.agora_channel)

        logger.info(f"[{self.session_id}] Voice session closed successfully")
