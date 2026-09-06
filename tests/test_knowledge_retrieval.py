"""Unit tests for KnowledgeRetrievalEngine (Partial RAG)."""

import pytest
import time
from backend.app.integrations.knowledge_retrieval import (
    KnowledgeRetrievalEngine,
    KnowledgeChunk,
    DEALERSHIP_KNOWLEDGE_BASE,
)


@pytest.fixture
def engine():
    return KnowledgeRetrievalEngine(chunks=DEALERSHIP_KNOWLEDGE_BASE)


@pytest.mark.asyncio
async def test_query_return_policy(engine):
    results = await engine.query("what is your 7 day return policy or refund guarantee?")
    assert len(results) > 0
    top_match = results[0]
    assert top_match.category == "policy"
    assert "7-day" in top_match.content.lower() or "500-kilometer" in top_match.content.lower()


@pytest.mark.asyncio
async def test_query_warranty(engine):
    results = await engine.query("do you offer extended warranty on luxury cars?")
    assert len(results) > 0
    top_match = results[0]
    assert top_match.category == "warranty"
    assert "3-year" in top_match.content or "star shield" in top_match.content.lower()


@pytest.mark.asyncio
async def test_query_financing_and_emi(engine):
    results = await engine.query("what are the interest rates and down payment with HDFC or ICICI?")
    assert len(results) > 0
    top_match = results[0]
    assert top_match.category == "financing"
    assert "7.99%" in top_match.content or "down payment" in top_match.content.lower()


@pytest.mark.asyncio
async def test_query_ev_charging(engine):
    results = await engine.query("does an electric car come with a home wallbox charger?")
    assert len(results) > 0
    top_match = results[0]
    assert top_match.category == "ev_charging"
    assert "wallbox" in top_match.content.lower()


@pytest.mark.asyncio
async def test_query_irrelevant_text_returns_empty_or_low_score(engine):
    # Irrelevant query should not trigger false positives
    results = await engine.query("what is the recipe for chocolate cake?")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_retrieval_latency_benchmark(engine):
    start = time.perf_counter()
    for _ in range(100):
        await engine.query("can I trade in my old car for exchange bonus?")
    elapsed_ms = (time.perf_counter() - start) * 1000.0 / 100.0

    # Ensure in-memory partial RAG lookup takes under 2ms per query
    assert elapsed_ms < 2.0, f"Retrieval took {elapsed_ms:.3f}ms, expected < 2.0ms"


def test_format_retrieval_prompt(engine):
    chunks = [
        KnowledgeChunk(
            chunk_id="test-1",
            category="policy",
            title="Test Policy",
            content="Always be helpful.",
        )
    ]
    formatted = engine.format_retrieval_prompt(chunks)
    assert "### Authoritative Dealership Policies" in formatted
    assert "[Test Policy]" in formatted
    assert "Always be helpful." in formatted
