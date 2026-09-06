"""Generation ID Controller for EchoDrive.

Guarantees that every generated response owns a unique generation identifier.
Audio/tokens from an obsolete generation are rejected to eliminate ghost/stale audio.
"""

import uuid
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GenerationController:
    """Manages active generation lifecycle and provides generation validity checks."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._active_generation_id: str = self._generate_id()
        self._generation_counter: int = 1

    def _generate_id(self) -> str:
        return f"gen_{uuid.uuid4().hex[:12]}"

    @property
    def active_generation_id(self) -> str:
        return self._active_generation_id

    @property
    def generation_counter(self) -> int:
        return self._generation_counter

    def is_valid(self, generation_id: str) -> bool:
        """Check if the given generation_id matches the currently active generation."""
        return bool(generation_id and generation_id == self._active_generation_id)

    def next_generation(self) -> str:
        """Advance to a brand new generation ID."""
        self._generation_counter += 1
        old_id = self._active_generation_id
        self._active_generation_id = self._generate_id()
        logger.info(f"[{self.session_id}] Advanced Generation: {old_id} -> {self._active_generation_id} (count={self._generation_counter})")
        return self._active_generation_id

    def invalidate(self) -> tuple[str, str]:
        """Invalidate the current generation and immediately allocate a new active generation ID.
        
        Returns:
            tuple of (old_generation_id, new_generation_id)
        """
        old_id = self._active_generation_id
        new_id = self.next_generation()
        logger.info(f"[{self.session_id}] Invalidated generation {old_id}, new active generation is {new_id}")
        return old_id, new_id
