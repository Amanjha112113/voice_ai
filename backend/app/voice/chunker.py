"""Progressive Sentence & Clause Chunker for EchoDrive.

Positioned strictly between LLM Token Stream and TTS.
Extracts natural syntactic phrases incrementally so TTS synthesis can start
on the very first clause without waiting for the full LLM completion.

Enforces strict protection for:
- Decimal numbers across streaming tokens (e.g. "₹24.54 Lakh", "15.5 kmpl")
- Comma-formatted Indian currency numbers (e.g. "₹1,50,000", "75,00,000")
- Common automotive & English abbreviations ("Rs.", "approx.", "e.g.", "Dr.")
- Currency symbols and trailing units
"""

import re
from typing import Generator, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Common abbreviations to prevent premature splitting
ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.",
    "e.g.", "i.e.", "etc.", "vs.", "approx.", "est.",
    "rs.", "inr.", "km.", "lakh.", "cr.", "no.", "vol.", "inc."
}

# Delimiters indicating clause or sentence boundaries
PUNCTUATION_SPLIT_REGEX = re.compile(r'([.?!,;:\n]+)')


class StreamingChunker:
    """Incremental clause and sentence chunker for streaming LLM tokens."""

    def __init__(self, min_chunk_words: int = 6, max_chunk_words: int = 30) -> None:
        self.min_chunk_words = min_chunk_words
        self.max_chunk_words = max_chunk_words
        self._buffer: str = ""
        self._chunk_index: int = 0

    @property
    def chunk_index(self) -> int:
        return self._chunk_index

    def _is_abbreviation(self, text: str) -> bool:
        """Check if the text ends with a recognized abbreviation."""
        tokens = text.strip().split()
        if not tokens:
            return False
        last_word = tokens[-1].lower()
        return last_word in ABBREVIATIONS

    def process_token(self, delta: str) -> List[Tuple[str, int, bool]]:
        """Process an incoming LLM token delta and return any completed chunks.
        
        Returns:
            List of (chunk_text, chunk_index, is_final)
        """
        self._buffer += delta
        ready_chunks: List[Tuple[str, int, bool]] = []
        search_start = 0

        while True:
            match = PUNCTUATION_SPLIT_REGEX.search(self._buffer, search_start)
            if not match:
                break

            delim_start = match.start()
            delim_end = match.end()
            delimiter = self._buffer[delim_start:delim_end]

            candidate = self._buffer[:delim_end]
            remainder = self._buffer[delim_end:]

            # 1. Decimal number protection (e.g. "24.54" or "₹24." waiting for "54")
            # If period is preceded by digit:
            if "." in delimiter:
                char_before = self._buffer[delim_start - 1] if delim_start > 0 else ""
                char_after = remainder[0] if remainder else ""

                if char_before.isdigit():
                    # If remainder is empty, we must wait for next token to see if digits follow
                    if not remainder:
                        break
                    # If next character is a digit, it's definitely a decimal (e.g. 24.54) -> skip this period
                    if char_after.isdigit():
                        search_start = delim_end
                        continue

                # If period is at the very end of buffer, wait for whitespace/next token before cutting
                if not remainder:
                    break

                # True sentence boundary period should be followed by whitespace or newline
                if remainder and not remainder[0].isspace() and not remainder.startswith(("\n", '"', "'", ")", "]", "}")):
                    search_start = delim_end
                    continue

            # 2. Number with commas protection (e.g. "1,50,000" or "₹75,000")
            if "," in delimiter:
                char_before = self._buffer[delim_start - 1] if delim_start > 0 else ""
                char_after = remainder[0] if remainder else ""
                if char_before.isdigit() and (char_after.isdigit() or not remainder):
                    if not remainder:
                        break
                    search_start = delim_end
                    continue

            # 3. Abbreviation check (e.g. "Rs. 24 Lakh" or "approx. 18 kmpl")
            if self._is_abbreviation(candidate):
                search_start = delim_end
                continue

            # 4. Check minimum words for weak punctuation (comma, semicolon, colon)
            words = candidate.strip().split()
            if len(words) < self.min_chunk_words and any(c in delimiter for c in [',', ';', ':']):
                # If there's more text coming, don't split on a tiny clause like "Well,"
                if remainder:
                    search_start = delim_end
                    continue
                else:
                    break

            # Valid chunk found
            chunk_text = candidate.strip()
            if chunk_text:
                self._chunk_index += 1
                ready_chunks.append((chunk_text, self._chunk_index, False))
                logger.debug(f"Chunker produced chunk #{self._chunk_index}: '{chunk_text}'")

            self._buffer = remainder
            search_start = 0

        return ready_chunks

    def flush(self) -> List[Tuple[str, int, bool]]:
        """Flush any remaining text in the buffer when LLM finishes generation."""
        ready_chunks: List[Tuple[str, int, bool]] = []
        remaining_text = self._buffer.strip()
        self._buffer = ""

        if remaining_text:
            self._chunk_index += 1
            ready_chunks.append((remaining_text, self._chunk_index, True))
            logger.debug(f"Chunker flushed final chunk #{self._chunk_index}: '{remaining_text}'")

        return ready_chunks

    def reset(self) -> None:
        """Reset internal buffer and chunk index."""
        self._buffer = ""
        self._chunk_index = 0
