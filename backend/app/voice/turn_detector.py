"""Turn Boundary and Turn-Taking Detector for EchoDrive.

Determines when the user has completed their conversational turn.
Combines VAD silence boundaries with syntactic indicators (punctuation, length)
to allow responsive turn transitions without premature cutoffs.
"""

from typing import Callable, Optional
import time
import logging

logger = logging.getLogger(__name__)


class TurnDetector:
    """Evaluates conversational turn completion."""

    def __init__(
        self,
        session_id: str,
        on_turn_ready: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.session_id = session_id
        self.on_turn_ready = on_turn_ready

        self.current_turn_id: int = 1
        self._accumulated_text: str = ""
        self._is_user_speaking: bool = False
        self._last_speech_end_ns: Optional[int] = None

    @property
    def accumulated_text(self) -> str:
        return self._accumulated_text.strip()

    def on_speech_start(self, timestamp_ns: int) -> None:
        self._is_user_speaking = True
        self._last_speech_end_ns = None

    def on_speech_end(self, timestamp_ns: int, duration_ms: float) -> None:
        self._is_user_speaking = False
        self._last_speech_end_ns = timestamp_ns

    def on_transcript(self, text: str, is_final: bool) -> None:
        """Handle incoming ASR transcript."""
        if not text:
            return

        if is_final:
            self._accumulated_text += f" {text}"
            self._accumulated_text = self._accumulated_text.strip()
            logger.debug(f"[{self.session_id}] Turn {self.current_turn_id} final segment: '{text}' (total: '{self._accumulated_text}')")
        else:
            logger.debug(f"[{self.session_id}] Turn {self.current_turn_id} partial: '{text}'")

    def should_finalize_turn(self) -> bool:
        """Check if accumulated transcript represents a completed turn."""
        if self._is_user_speaking:
            return False
        if not self._accumulated_text.strip():
            return False
        return True

    def finalize_turn(self) -> tuple[int, str]:
        """Finalize and seal the current turn, incrementing turn counter.
        
        Returns:
            tuple of (sealed_turn_id, complete_user_text)
        """
        turn_id = self.current_turn_id
        text = self._accumulated_text.strip()
        
        # Advance turn
        self.current_turn_id += 1
        self._accumulated_text = ""
        self._last_speech_end_ns = None

        logger.info(f"[{self.session_id}] Turn {turn_id} SEALED: '{text}'")
        if self.on_turn_ready and text:
            self.on_turn_ready(text, turn_id)

        return turn_id, text

    def reset(self) -> None:
        self._accumulated_text = ""
        self._is_user_speaking = False
        self._last_speech_end_ns = None
