"""Session Management API Routes for EchoDrive Control Plane."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from ..voice.session_manager import session_manager
from ..providers.mock_providers import MockASRProvider, MockLLMProvider, MockTTSProvider
from ..providers.openai_llm import OpenAILLMProvider
from ..providers.groq_llm import GroqLLMProvider
from ..providers.deepgram_asr import DeepgramASRProvider
from ..providers.cartesia_tts import CartesiaTTSProvider
from ..providers.elevenlabs_tts import ElevenLabsTTSProvider
from ..config.settings import settings

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    customer_id: Optional[str] = Field(default=None, description="Optional customer ID")
    language: str = Field(default="en-IN", description="Spoken language code")
    use_mock_providers: bool = Field(default=False, description="Use deterministic mocks for testing/benchmarking")


class CreateSessionResponse(BaseModel):
    session_id: str
    channel: str
    token: str
    app_id: str
    status: str
    language: str


class SessionDetailResponse(BaseModel):
    session_id: str
    channel: str
    status: str
    current_state: str
    active_generation_id: str
    generation_counter: int
    interruption_count: int
    stale_chunks_rejected: int
    total_turns: int
    metrics_summary: Dict[str, Any]


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest):
    """Create a new Voice Session and provision Agora RTC channel and access token."""
    # Provider selection
    if request.use_mock_providers:
        asr = MockASRProvider()
        llm = MockLLMProvider()
        tts = MockTTSProvider()
    else:
        asr = DeepgramASRProvider(language=request.language)
        
        # LLM Provider selection: Groq (if key set) or OpenAI
        if settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"):
            llm = GroqLLMProvider()
        else:
            llm = OpenAILLMProvider()

        # TTS Provider selection: ElevenLabs (if key set) or Cartesia
        if settings.ELEVENLABS_API_KEY and not settings.ELEVENLABS_API_KEY.startswith("your_"):
            tts = ElevenLabsTTSProvider()
        else:
            tts = CartesiaTTSProvider()

    session = await session_manager.create_session(
        customer_id=request.customer_id,
        language=request.language,
        asr_provider=asr,
        llm_provider=llm,
        tts_provider=tts,
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        channel=session.agora_channel,
        token=session.agora_token,
        app_id=settings.AGORA_APP_ID,
        status="starting",
        language=session.language,
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str):
    """Retrieve detailed state, metrics, and generation information for an active session."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    summary = session.metrics_collector.summary()
    return SessionDetailResponse(
        session_id=session.session_id,
        channel=session.agora_channel,
        status="active" if not session.is_closed else "closed",
        current_state=session.state_machine.current_state.value,
        active_generation_id=session.generation_controller.active_generation_id,
        generation_counter=session.generation_controller.generation_counter,
        interruption_count=session.cancellation.interruption_count,
        stale_chunks_rejected=session.audio_output.stale_chunks_rejected,
        total_turns=summary["total_turns"],
        metrics_summary=summary,
    )


class ProcessTurnRequest(BaseModel):
    user_text: str = Field(..., description="User transcript or speech input")
    turn_id: Optional[int] = Field(default=None, description="Optional turn counter")


@router.post("/{session_id}/turns")
async def process_turn(session_id: str, request: ProcessTurnRequest):
    """Process a conversational voice turn through the live pipeline."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    turn_id = request.turn_id or session.turn_detector.current_turn_id
    from ..voice.pipeline import VoicePipeline

    telemetry = await VoicePipeline.process_user_turn(
        session=session,
        user_text=request.user_text,
        turn_id=turn_id,
    )

    return {
        "session_id": session_id,
        "turn_id": turn_id,
        "generation_id": telemetry.generation_id,
        "ttfa_ms": telemetry.ttfa_ms,
        "llm_ttft_ms": telemetry.llm_ttft_ms,
        "status": "completed",
    }


@router.post("/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    """Trigger immediate barge-in interruption for an active session."""
    session = await session_manager.get_session(session_id)
    if not session:
        return {
            "session_id": session_id,
            "status": "already_closed",
            "stop_latency_ms": 0.0,
        }

    stop_latency = await session.cancellation.interrupt(reason="manual_barge_in_request")
    return {
        "session_id": session_id,
        "status": "interrupted",
        "stop_latency_ms": stop_latency,
        "active_generation_id": session.generation_controller.active_generation_id,
    }


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(session_id: str):
    """Terminate session and cancel all associated tasks."""
    deleted = await session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return {"message": f"Session '{session_id}' successfully terminated and cleaned up."}
