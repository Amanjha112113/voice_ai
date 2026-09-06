"""Unit tests for StreamingChunker."""

import pytest
from backend.app.voice.chunker import StreamingChunker


def test_chunker_punctuation_splitting():
    chunker = StreamingChunker(min_chunk_words=2)
    tokens = ["Hello ", "there! ", "How ", "can ", "I ", "help ", "you ", "today?"]

    chunks = []
    for token in tokens:
        ready = chunker.process_token(token)
        chunks.extend(ready)

    flushed = chunker.flush()
    chunks.extend(flushed)

    texts = [c[0] for c in chunks]
    assert "Hello there!" in texts
    assert "How can I help you today?" in texts


def test_chunker_abbreviation_and_decimal_protection():
    chunker = StreamingChunker(min_chunk_words=2)
    # Ensure "Rs. 15.5 Lakh" is not split prematurely
    tokens = ["The ", "price ", "is ", "Rs. ", "15.5 ", "Lakh ", "for ", "this ", "variant. "]

    chunks = []
    for token in tokens:
        ready = chunker.process_token(token)
        chunks.extend(ready)

    flushed = chunker.flush()
    chunks.extend(flushed)

    texts = [c[0] for c in chunks]
    # Should produce full sentence without breaking at "Rs." or "15.5"
    assert len(texts) == 1
    assert "The price is Rs. 15.5 Lakh for this variant." in texts[0]


def test_chunker_flush_remainder():
    chunker = StreamingChunker(min_chunk_words=2)
    tokens = ["Sure thing I can check that for you right now"] # No terminal punctuation

    chunks = []
    for token in tokens:
        ready = chunker.process_token(token)
        chunks.extend(ready)

    assert len(chunks) == 0  # No punctuation split yet

    flushed = chunker.flush()
    assert len(flushed) == 1
    assert flushed[0][0] == "Sure thing I can check that for you right now"
    assert flushed[0][2] is True  # is_final is True


def test_chunker_streaming_decimal_split():
    chunker = StreamingChunker(min_chunk_words=3)
    # Simulate LLM token stream splitting right at the decimal point "₹24." then "54"
    tokens = [
        "The ", "Mahindra ", "Scorpio ", "is ", "priced ", "at ", "₹24.",
        "54 ", "Lakh ", "ex-showroom ", "(≈₹29.", "5 ", "Lakh ", "on-road). ",
        "Would ", "you ", "like ", "to ", "book ", "a ", "test ", "drive?"
    ]

    chunks = []
    for token in tokens:
        ready = chunker.process_token(token)
        chunks.extend(ready)

    flushed = chunker.flush()
    chunks.extend(flushed)

    texts = [c[0] for c in chunks]
    # Verify that "₹24.54 Lakh" and "₹29.5 Lakh" were NOT split into "₹24." and "54"
    assert not any(t.endswith("₹24.") for t in texts)
    assert not any(t.startswith("54") for t in texts)
    assert any("₹24.54 Lakh" in t for t in texts)
    assert any("₹29.5 Lakh" in t for t in texts)

