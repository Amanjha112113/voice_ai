"""Telemetry and Human-Readable Turn Latency Trace for EchoDrive.

Uses high-resolution monotonic timestamps (time.perf_counter_ns) internally,
and formats metrics and traces in milliseconds (ms).
"""

from dataclasses import dataclass, field
import time
from typing import Optional, List, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class InterruptionTelemetry:
    """Stores high-resolution boundary timestamps for an entire interruption lifecycle."""
    session_id: str
    turn_id: int
    interrupted_generation_id: str
    new_generation_id: str
    speech_detected_ns: int
    generation_invalidated_ns: Optional[int] = None
    llm_cancel_requested_ns: Optional[int] = None
    tts_cancel_requested_ns: Optional[int] = None
    audio_buffer_flushed_ns: Optional[int] = None
    playback_stopped_ns: Optional[int] = None
    ack_started_ns: Optional[int] = None
    ack_finished_ns: Optional[int] = None
    user_speech_finished_ns: Optional[int] = None
    asr_final_ns: Optional[int] = None
    new_generation_started_ns: Optional[int] = None

    @property
    def stop_latency_ms(self) -> float:
        """Latency from speech detected to playback stopped and buffer flushed."""
        stop_ts = self.playback_stopped_ns or self.audio_buffer_flushed_ns or self.speech_detected_ns
        return (stop_ts - self.speech_detected_ns) / 1_000_000.0

    def __float__(self) -> float:
        return self.stop_latency_ms

    def __ge__(self, other: Any) -> bool:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return self.stop_latency_ms >= val

    def __le__(self, other: Any) -> bool:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return self.stop_latency_ms <= val

    def __gt__(self, other: Any) -> bool:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return self.stop_latency_ms > val

    def __lt__(self, other: Any) -> bool:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return self.stop_latency_ms < val

    def __mul__(self, other: Any) -> float:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return self.stop_latency_ms * val

    def __rmul__(self, other: Any) -> float:
        val = float(other.stop_latency_ms) if isinstance(other, InterruptionTelemetry) else float(other)
        return val * self.stop_latency_ms

    @property
    def ack_duration_ms(self) -> Optional[float]:
        if self.ack_started_ns and self.ack_finished_ns:
            return (self.ack_finished_ns - self.ack_started_ns) / 1_000_000.0
        return None

    def format_detailed_trace(self) -> str:
        """Produce a complete millisecond timeline trace matching production audit requirements."""
        base = self.speech_detected_ns
        def rel_ms(ts: Optional[int]) -> str:
            if ts is None:
                return "    -- ms"
            diff = (ts - base) / 1_000_000.0
            return f"{diff:6.2f} ms"

        lines = [
            f"\n⚡ === DEEP INTERRUPTION TIMELINE (Session: {self.session_id}, Turn #{self.turn_id}) ===",
            f"speech_detected            {rel_ms(self.speech_detected_ns)}",
            f"generation_invalidated     {rel_ms(self.generation_invalidated_ns)}  [old={self.interrupted_generation_id[:8]} -> new={self.new_generation_id[:8]}]",
            f"llm_cancel_requested       {rel_ms(self.llm_cancel_requested_ns)}",
            f"tts_cancel_requested       {rel_ms(self.tts_cancel_requested_ns)}",
            f"audio_buffer_flushed       {rel_ms(self.audio_buffer_flushed_ns)}",
            f"playback_stopped           {rel_ms(self.playback_stopped_ns)}",
            f"ack_started                {rel_ms(self.ack_started_ns)}  [Phrase: 'OK.']",
            f"ack_finished               {rel_ms(self.ack_finished_ns)}",
            f"user_speech_finished       {rel_ms(self.user_speech_finished_ns)}",
            f"asr_final                  {rel_ms(self.asr_final_ns)}",
            f"new_generation_started     {rel_ms(self.new_generation_started_ns)}",
            "--------------------------------------------------------------------------------",
            f"Interruption-Stop Latency: {self.stop_latency_ms:.2f} ms (Target ≤ 200 ms)",
            "================================================================================\n"
        ]
        return "\n".join(lines)


@dataclass
class TurnTelemetry:
    """Stores boundary timestamps for a single conversational turn."""
    turn_id: int
    generation_id: str
    speech_start_ns: Optional[int] = None
    speech_end_ns: Optional[int] = None
    asr_final_ns: Optional[int] = None
    llm_request_ns: Optional[int] = None
    llm_ttft_ns: Optional[int] = None      # Time to first token
    tts_request_ns: Optional[int] = None
    tts_first_audio_ns: Optional[int] = None # Time to first TTS audio chunk
    first_audio_played_ns: Optional[int] = None # TTFA boundary
    turn_complete_ns: Optional[int] = None

    # Interruption timestamps
    interruption_detected_ns: Optional[int] = None
    generation_invalidated_ns: Optional[int] = None
    llm_cancelled_ns: Optional[int] = None
    tts_cancelled_ns: Optional[int] = None
    playback_stopped_ns: Optional[int] = None

    @property
    def ttfa_ms(self) -> Optional[float]:
        """Time to First Audio (from user speech completion to first AI audio played)."""
        ref_start = self.speech_end_ns or self.asr_final_ns
        if ref_start and self.first_audio_played_ns and self.first_audio_played_ns >= ref_start:
            return (self.first_audio_played_ns - ref_start) / 1_000_000.0
        return None

    @property
    def asr_latency_ms(self) -> Optional[float]:
        if self.speech_end_ns and self.asr_final_ns:
            return (self.asr_final_ns - self.speech_end_ns) / 1_000_000.0
        return None

    @property
    def llm_ttft_ms(self) -> Optional[float]:
        if self.llm_request_ns and self.llm_ttft_ns:
            return (self.llm_ttft_ns - self.llm_request_ns) / 1_000_000.0
        return None

    @property
    def tts_first_audio_latency_ms(self) -> Optional[float]:
        if self.tts_request_ns and self.tts_first_audio_ns:
            return (self.tts_first_audio_ns - self.tts_request_ns) / 1_000_000.0
        return None

    @property
    def interruption_stop_ms(self) -> Optional[float]:
        if self.interruption_detected_ns and self.playback_stopped_ns:
            return (self.playback_stopped_ns - self.interruption_detected_ns) / 1_000_000.0
        return None

    def format_turn_trace(self) -> str:
        """Produce a human-readable latency trace in milliseconds."""
        base = self.speech_start_ns or self.speech_end_ns or self.asr_final_ns or 0
        def rel_ms(ts: Optional[int]) -> str:
            if ts is None or base == 0:
                return "--"
            return f"{(ts - base) / 1_000_000.0:6.1f} ms"

        lines = [
            f"\n=== TURN #{self.turn_id} (gen={self.generation_id}) ===",
            f"Speech start       {rel_ms(self.speech_start_ns)}",
            f"Speech end         {rel_ms(self.speech_end_ns)}",
            f"ASR final          {rel_ms(self.asr_final_ns)}",
            f"LLM first token    {rel_ms(self.llm_ttft_ns)}",
            f"TTS first audio    {rel_ms(self.tts_first_audio_ns)}",
            f"Audio playback     {rel_ms(self.first_audio_played_ns)}",
            "---------------------------------------",
            f"TTFA:              {self.ttfa_ms:.1f} ms" if self.ttfa_ms is not None else "TTFA:              --",
            "=======================================\n"
        ]
        return "\n".join(lines)

    def format_interruption_trace(self) -> str:
        """Produce a human-readable interruption timeline."""
        base = self.interruption_detected_ns or 0
        def rel_ms(ts: Optional[int]) -> str:
            if ts is None or base == 0:
                return "--"
            return f"{(ts - base) / 1_000_000.0:5.1f} ms"

        lines = [
            f"\n⚡ === INTERRUPTION TRACE (Turn #{self.turn_id}) ===",
            "AI speaking",
            "     ↓",
            f"User interruption detected   {rel_ms(self.interruption_detected_ns)}",
            "     ↓",
            f"Generation invalidated       {rel_ms(self.generation_invalidated_ns)}",
            "     ↓",
            f"LLM cancelled                {rel_ms(self.llm_cancelled_ns)}",
            "     ↓",
            f"TTS cancelled                {rel_ms(self.tts_cancelled_ns)}",
            "     ↓",
            f"Playback stopped             {rel_ms(self.playback_stopped_ns)}",
            "---------------------------------------",
            f"Interruption latency:        {self.interruption_stop_ms:.1f} ms" if self.interruption_stop_ms is not None else "Interruption latency:        --",
            "=======================================\n"
        ]
        return "\n".join(lines)
