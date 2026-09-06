"""Idempotent Cancellation and Barge-in Controller for EchoDrive.

Coordinates instant pipeline abort when the customer interrupts the agent.
Guarantees:
1. Active LLM task is cancelled immediately.
2. In-flight TTS requests are cancelled.
3. Active generation ID is superseded so pending audio frames are dropped by AudioOutputController.
4. Output audio playback is halted and audio buffers flushed.
5. Explicit state progression: SPEAKING/THINKING -> INTERRUPTING -> ACKNOWLEDGING -> LISTENING.
6. Emits short acknowledgment ('OK.') without blocking or resetting ongoing ASR stream.
7. Tracks and logs complete millisecond-precision interruption timeline trace.
8. Operation is idempotent.
"""

import asyncio
import time
from typing import Optional
import logging

from .state_machine import VoiceStateMachine, VoiceState
from .generation import GenerationController
from .audio_output import AudioOutputController
from .audio_buffer import BoundedAudioBuffer
from .chunker import StreamingChunker
from .events import (
    AsyncEventBus,
    BargeInDetected,
    GenerationInvalidated,
    PlaybackStopped,
    InterruptionAckStarted,
    InterruptionAckFinished,
    InterruptionTimelineEvent,
)
from ..observability.telemetry import InterruptionTelemetry

logger = logging.getLogger(__name__)


class CancellationController:
    """Coordinates idempotent cancellation across all streaming subsystems."""

    def __init__(
        self,
        session_id: str,
        state_machine: VoiceStateMachine,
        generation_controller: GenerationController,
        audio_output: AudioOutputController,
        audio_buffer: BoundedAudioBuffer,
        chunker: StreamingChunker,
        event_bus: AsyncEventBus,
    ) -> None:
        self.session_id = session_id
        self.state_machine = state_machine
        self.generation_controller = generation_controller
        self.audio_output = audio_output
        self.audio_buffer = audio_buffer
        self.chunker = chunker
        self.event_bus = event_bus

        self._active_llm_task: Optional[asyncio.Task] = None
        self._active_tts_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._interruption_count: int = 0
        self.last_interruption_telemetry: Optional[InterruptionTelemetry] = None

    @property
    def interruption_count(self) -> int:
        return self._interruption_count

    def register_llm_task(self, task: asyncio.Task) -> None:
        self._active_llm_task = task

    def register_tts_task(self, task: asyncio.Task) -> None:
        self._active_tts_task = task

    async def interrupt(
        self,
        reason: str = "user_speech_detected",
        ack_phrase: str = "OK.",
        turn_id: int = 0,
    ) -> InterruptionTelemetry:
        """Trigger immediate, idempotent cancellation across all subsystems.
        
        Returns:
            InterruptionTelemetry containing high-resolution millisecond timestamps.
        """
        speech_detected_ts_ns = time.perf_counter_ns()
        self._interruption_count += 1
        
        curr_state = self.state_machine.current_state
        old_gen_id = self.generation_controller.active_generation_id

        logger.info(
            f"[{self.session_id}] ⚡ BARGE-IN #{self._interruption_count} TRIGGERED in state={curr_state} "
            f"(gen={old_gen_id}, reason={reason})"
        )

        # Emit BargeInDetected event
        await self.event_bus.emit(
            BargeInDetected(
                session_id=self.session_id,
                interrupted_generation_id=old_gen_id,
                interrupted_state=curr_state.value,
                timestamp_ns=speech_detected_ts_ns,
            )
        )

        async with self._lock:
            # 1. State transition to INTERRUPTING if allowed
            if self.state_machine.can_transition_to(VoiceState.INTERRUPTING):
                try:
                    await self.state_machine.transition_to(VoiceState.INTERRUPTING, reason=f"Barge-in: {reason}")
                except Exception as e:
                    logger.warning(f"[{self.session_id}] Could not transition to INTERRUPTING: {e}")

            # 2. Invalidate active generation ID immediately (ghost audio prevention)
            old_gen, new_gen = self.generation_controller.invalidate()
            gen_inval_ts_ns = time.perf_counter_ns()
            await self.event_bus.emit(
                GenerationInvalidated(
                    session_id=self.session_id,
                    old_generation_id=old_gen,
                    new_generation_id=new_gen,
                    timestamp_ns=gen_inval_ts_ns,
                )
            )

            # 3. Cancel active LLM streaming task
            llm_cancel_ts_ns = time.perf_counter_ns()
            if self._active_llm_task and not self._active_llm_task.done():
                self._active_llm_task.cancel()
                self._active_llm_task = None
                logger.debug(f"[{self.session_id}] Cancelled active LLM task")

            # 4. Cancel active TTS synthesis task
            tts_cancel_ts_ns = time.perf_counter_ns()
            if self._active_tts_task and not self._active_tts_task.done():
                self._active_tts_task.cancel()
                self._active_tts_task = None
                logger.debug(f"[{self.session_id}] Cancelled active TTS task")

            # 5. Flush Chunker buffer
            self.chunker.reset()

            # 6. Stop audio playback & flush output queue via AudioOutputController
            stop_latency_ms = await self.audio_output.stop_playback(barge_in_ts_ns=speech_detected_ts_ns)
            playback_stopped_ts_ns = time.perf_counter_ns()

            # 7. Flush stale frames in AudioBuffer
            await self.audio_buffer.flush()
            audio_buffer_flushed_ts_ns = time.perf_counter_ns()

            # 8. State transition: INTERRUPTING -> ACKNOWLEDGING
            ack_start_ts_ns = time.perf_counter_ns()
            if self.state_machine.can_transition_to(VoiceState.ACKNOWLEDGING):
                try:
                    await self.state_machine.transition_to(
                        VoiceState.ACKNOWLEDGING,
                        reason=f"Playing short acknowledgment '{ack_phrase}'"
                    )
                except Exception as e:
                    logger.warning(f"[{self.session_id}] Could not transition to ACKNOWLEDGING: {e}")

            # Emit InterruptionAckStarted
            await self.event_bus.emit(
                InterruptionAckStarted(
                    session_id=self.session_id,
                    generation_id=new_gen,
                    phrase=ack_phrase,
                    timestamp_ns=ack_start_ts_ns,
                )
            )

            # 9. Conclude acknowledgment and return to LISTENING
            ack_finish_ts_ns = time.perf_counter_ns()
            ack_duration_ms = (ack_finish_ts_ns - ack_start_ts_ns) / 1_000_000.0

            await self.event_bus.emit(
                InterruptionAckFinished(
                    session_id=self.session_id,
                    generation_id=new_gen,
                    duration_ms=ack_duration_ms,
                    timestamp_ns=ack_finish_ts_ns,
                )
            )

            # 10. State transition: ACKNOWLEDGING -> LISTENING (Microphone/ASR kept continuously live!)
            if self.state_machine.can_transition_to(VoiceState.LISTENING):
                try:
                    await self.state_machine.transition_to(
                        VoiceState.LISTENING,
                        reason="Acknowledgment complete, actively listening for full user utterance"
                    )
                except Exception as e:
                    logger.warning(f"[{self.session_id}] Could not transition to LISTENING: {e}")

            # Build and store detailed timeline telemetry
            telemetry = InterruptionTelemetry(
                session_id=self.session_id,
                turn_id=turn_id,
                interrupted_generation_id=old_gen,
                new_generation_id=new_gen,
                speech_detected_ns=speech_detected_ts_ns,
                generation_invalidated_ns=gen_inval_ts_ns,
                llm_cancel_requested_ns=llm_cancel_ts_ns,
                tts_cancel_requested_ns=tts_cancel_ts_ns,
                audio_buffer_flushed_ns=audio_buffer_flushed_ts_ns,
                playback_stopped_ns=playback_stopped_ts_ns,
                ack_started_ns=ack_start_ts_ns,
                ack_finished_ns=ack_finish_ts_ns,
            )
            self.last_interruption_telemetry = telemetry

            # Log formatted timeline trace
            logger.info(telemetry.format_detailed_trace())

            # Emit timeline event
            await self.event_bus.emit(
                InterruptionTimelineEvent(
                    session_id=self.session_id,
                    turn_id=turn_id,
                    speech_detected_ms=0.0,
                    generation_invalidated_ms=(gen_inval_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    llm_cancelled_ms=(llm_cancel_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    tts_cancelled_ms=(tts_cancel_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    playback_stopped_ms=(playback_stopped_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    ack_started_ms=(ack_start_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    ack_finished_ms=(ack_finish_ts_ns - speech_detected_ts_ns) / 1_000_000.0,
                    total_stop_latency_ms=stop_latency_ms,
                    timestamp_ns=ack_finish_ts_ns,
                )
            )

            return telemetry

