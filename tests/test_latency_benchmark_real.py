"""Real-World Provider & Agora Latency Benchmark Harness for EchoDrive.

Executes real live API calls against Deepgram, OpenAI, Cartesia, and Agora RTC
when credentials are provided in the environment / .env file.
"""

import asyncio
import os
import pytest
from backend.app.config.settings import settings
from backend.app.voice.session import VoiceSession
from backend.app.voice.pipeline import VoicePipeline
from backend.app.providers.deepgram_asr import DeepgramASRProvider
from backend.app.providers.openai_llm import OpenAILLMProvider
from backend.app.providers.groq_llm import GroqLLMProvider
from backend.app.providers.cartesia_tts import CartesiaTTSProvider
from backend.app.providers.elevenlabs_tts import ElevenLabsTTSProvider
from backend.app.providers.agora_rtc import AgoraRTCGateway
from backend.app.observability.metrics import MetricsCollector


async def run_real_benchmark(num_turns: int = 5):
    """Run real live provider calls if API keys are set."""
    collector = MetricsCollector()
    rtc = AgoraRTCGateway()
    token = rtc.generate_token("live_benchmark_room", uid=1001)

    # Select LLM: Groq or OpenAI
    if settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"):
        llm = GroqLLMProvider()
    elif settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
        llm = OpenAILLMProvider()
    else:
        print("⚠️ No live LLM API key configured (neither GROQ_API_KEY nor OPENAI_API_KEY).")
        return None

    # Select TTS: ElevenLabs or Cartesia
    if settings.ELEVENLABS_API_KEY and not settings.ELEVENLABS_API_KEY.startswith("your_"):
        tts = ElevenLabsTTSProvider()
    else:
        tts = CartesiaTTSProvider()

    session = VoiceSession(
        session_id="real_benchmark_sess",
        agora_channel="live_benchmark_room",
        agora_token=token,
        asr_provider=DeepgramASRProvider(),
        llm_provider=llm,
        tts_provider=tts,
        rtc_gateway=rtc,
    )

    print(f"\n🌐 Running Real-World Provider Benchmark ({num_turns} turns)...")
    prompts = [
        "I need a spacious SUV under 20 lakh with great mileage.",
        "Can you compare the Scorpio N with the Grand Vitara?",
        "What are the safety ratings for the Mahindra Scorpio?",
        "Does the top variant come with 6 airbags and a sunroof?",
        "I would like to book a test drive for this weekend.",
    ]

    try:
        for turn_idx, prompt in enumerate(prompts[:num_turns], start=1):
            print(f"\n--- Processing Turn {turn_idx}: '{prompt}' ---")
            telemetry = await VoicePipeline.process_user_turn(
                session=session,
                user_text=prompt,
                turn_id=turn_idx,
            )
            collector.record_turn(telemetry)
    except Exception as e:
        print(f"⚠️ Live provider benchmark notice: {e}")
    finally:
        await session.close()

    return collector


@pytest.mark.asyncio
async def test_live_providers_optional():
    """Optional live test when API keys are available."""
    has_llm = (
        (settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"))
        or (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_") and settings.OPENAI_API_KEY != "dummy-key")
    )
    if has_llm:
        collector = await run_real_benchmark(num_turns=2)
        if collector and collector.turn_count > 0:
            print("\n" + collector.format_summary_table())


if __name__ == "__main__":
    collector = asyncio.run(run_real_benchmark(num_turns=5))
    if collector:
        print("\n" + collector.format_summary_table())
