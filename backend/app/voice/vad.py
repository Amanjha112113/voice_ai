"""Voice Activity Detection (VAD) for EchoDrive.

Uses a dual-window sliding probe algorithm:
- Prefix Window (e.g. 60ms = 3x 20ms frames) for fast speech onset detection (<60ms)
- Silence Window (e.g. 400ms = 20x 20ms frames) for speech completion detection
- Avoids duplicating Agora native VAD if present, while providing a pure-Python fallback.
"""

import math
import struct
from enum import Enum, auto
from typing import Callable, List, Optional
import time
import logging

logger = logging.getLogger(__name__)


class VADState(Enum):
    SILENCE = auto()
    SPEECH = auto()


class EnergyVAD:
    """Sliding-window Energy VAD with dual-window speech onset & trailing silence detection."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        energy_threshold: float = 0.02,
        prefix_padding_ms: int = 60,
        silence_duration_ms: int = 400,
        on_speech_start: Optional[Callable[[int], None]] = None,
        on_speech_end: Optional[Callable[[int, float], None]] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.energy_threshold = energy_threshold

        self.prefix_frames = max(1, prefix_padding_ms // frame_ms)
        self.silence_frames = max(1, silence_duration_ms // frame_ms)
        self.window_size = max(self.prefix_frames, self.silence_frames)

        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self.state: VADState = VADState.SILENCE
        self._probe_history: List[float] = []
        self._speech_start_ts: Optional[int] = None

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        """Compute Normalized Root Mean Square (RMS) energy of 16-bit PCM audio."""
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0

        try:
            # Unpack 16-bit signed little-endian integers
            samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
            sum_squares = sum(s * s for s in samples)
            mean_square = sum_squares / num_samples
            rms = math.sqrt(mean_square)
            # Normalize to 0.0 - 1.0 (max 16-bit value is 32767)
            return rms / 32768.0
        except Exception:
            return 0.0

    def process_frame(self, pcm_bytes: bytes) -> tuple[VADState, bool]:
        """Process a single 20ms audio frame and evaluate state transitions.
        
        Returns:
            tuple of (current_vad_state, transition_occurred_bool)
        """
        now_ns = time.perf_counter_ns()
        rms = self._compute_rms(pcm_bytes)
        self._probe_history.append(rms)
        if len(self._probe_history) > self.window_size:
            self._probe_history.pop(0)

        transition_occurred = False

        if self.state == VADState.SILENCE:
            # Check for transition to SPEECH (all prefix probes above threshold)
            if len(self._probe_history) >= self.prefix_frames:
                recent_probes = self._probe_history[-self.prefix_frames:]
                if all(p >= self.energy_threshold for p in recent_probes):
                    self.state = VADState.SPEECH
                    self._speech_start_ts = now_ns
                    transition_occurred = True
                    logger.debug("VAD Transition: SILENCE -> SPEECH")
                    if self.on_speech_start:
                        self.on_speech_start(now_ns)

        elif self.state == VADState.SPEECH:
            # Check for transition to SILENCE (all silence probes below threshold)
            if len(self._probe_history) >= self.silence_frames:
                recent_probes = self._probe_history[-self.silence_frames:]
                if all(p < self.energy_threshold for p in recent_probes):
                    self.state = VADState.SILENCE
                    transition_occurred = True
                    duration_ms = 0.0
                    if self._speech_start_ts:
                        duration_ms = (now_ns - self._speech_start_ts) / 1_000_000.0
                    logger.debug(f"VAD Transition: SPEECH -> SILENCE (speech duration: {duration_ms:.1f} ms)")
                    if self.on_speech_end:
                        self.on_speech_end(now_ns, duration_ms)

        return self.state, transition_occurred

    def reset(self) -> None:
        """Reset internal history."""
        self.state = VADState.SILENCE
        self._probe_history.clear()
        self._speech_start_ts = None
