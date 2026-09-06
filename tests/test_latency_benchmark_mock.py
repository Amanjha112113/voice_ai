"""Deterministic 100-Turn Latency Benchmark Harness for EchoDrive.

Runs 100 turns through the end-to-end streaming voice pipeline,
measuring and calculating P50, P95, and P99 percentiles for:
- TTFA (Time to First Audio)
- LLM TTFT (Time to First Token)
- TTS First Audio Latency
- Interruption Stop Latency
"""

import asyncio
import pytest
from backend.app.voice.session import VoiceSession
from backend.app.voice.pipeline import VoicePipeline
from backend.app.providers.mock_providers import MockASRProvider, MockLLMProvider, MockTTSProvider
from backend.app.observability.metrics import MetricsCollector


async def run_benchmark(num_turns: int = 100) -> MetricsCollector:
    """Execute continuous streaming turns and collect metrics."""
    collector = MetricsCollector()

    # Calibrated mock providers reflecting standard cloud provider streaming latencies:
    # LLM TTFT ~180ms, TTS first audio ~80ms
    session = VoiceSession(
        session_id="benchmark_session",
        asr_provider=MockASRProvider(latency_ms=60.0),
        llm_provider=MockLLMProvider(ttft_ms=180.0, token_interval_ms=12.0),
        tts_provider=MockTTSProvider(first_audio_ms=75.0, chunk_interval_ms=15.0),
    )

    print(f"\n🚀 Running EchoDrive Latency Benchmark ({num_turns} turns)...")

    for turn_idx in range(1, num_turns + 1):
        prompt = f"Turn {turn_idx}: I am looking for a 7 seater SUV with good mileage under 18 lakh."
        telemetry = await VoicePipeline.process_user_turn(
            session=session,
            user_text=prompt,
            turn_id=turn_idx,
        )
        collector.record_turn(telemetry)

        # Randomly perform barge-in on 10% of turns to benchmark interruption stop latency
        if turn_idx % 10 == 0:
            stop_lat = await session.cancellation.interrupt(reason="benchmark_barge_in")
            # Re-record with interruption latency
            telemetry.interruption_detected_ns = 0
            telemetry.playback_stopped_ns = int(stop_lat * 1_000_000)
            collector.record_turn(telemetry)

    await session.close()
    return collector


@pytest.mark.asyncio
async def test_latency_benchmark_100_turns():
    """Verify latency performance against MVP targets over 100 turns."""
    collector = await run_benchmark(num_turns=100)
    summary = collector.summary()

    print("\n" + collector.format_summary_table())

    # Assertions against acceptance criteria targets
    assert summary["total_turns"] >= 100
    assert summary["ttfa_ms"]["p50"] <= 700.0, f"TTFA P50 was {summary['ttfa_ms']['p50']}ms (target: <=700ms)"
    assert summary["llm_ttft_ms"]["p50"] <= 350.0, f"LLM TTFT P50 was {summary['llm_ttft_ms']['p50']}ms (target: <=350ms)"
    assert summary["tts_latency_ms"]["p50"] <= 150.0, f"TTS latency P50 was {summary['tts_latency_ms']['p50']}ms (target: <=150ms)"


if __name__ == "__main__":
    collector = asyncio.run(run_benchmark(num_turns=100))
    print("\n" + collector.format_summary_table())
