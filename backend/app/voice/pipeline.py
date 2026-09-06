"""Realtime Voice Pipeline for EchoDrive.

Orchestrates the continuous voice loop:
Customer → Agora → Audio Input → VAD / Turn Detect → ASR → RAG Lookup → LLM → Token Chunker → TTS → Audio Output Controller → Agora → Customer

Enforces:
- Authoritative dealership catalog grounding (zero price hallucination)
- Progressive phrase chunking for sub-700ms TTFA
- Explicit state transitions
- First-class generation ID tagging at every audio chunk
- Real-time latency boundary timestamping
- Idempotent interruption handling
- Async persistence and CRM lead qualification
"""

import asyncio
import time
import re
from typing import Optional, List, Dict
import logging

from .session import VoiceSession
from .state_machine import VoiceState
from .events import (
    LLMStarted, LLMToken, ChunkReady, TTSStarted, AudioChunk, TurnCompleted
)
from ..observability.telemetry import TurnTelemetry
from ..catalog.catalog_service import catalog_service
from ..integrations.knowledge_retrieval import knowledge_engine
from ..persistence import persistence_repo, LeadExtractor

logger = logging.getLogger(__name__)

# Fast-path pause/interruption phrases where an ultra-brief 'Sure.' is the optimal voice UX
PAUSE_PHRASES = {
    "wait", "wait wait", "wait wait wait", "hold on", "one second",
    "one sec", "just a second", "just a moment", "hang on", "pause",
    "stop", "wait a minute", "one minute", "give me a second"
}


class VoicePipeline:
    """Executes the streaming conversational response loop for a VoiceSession."""

    @staticmethod
    async def process_user_turn(
        session: VoiceSession,
        user_text: str,
        turn_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> TurnTelemetry:
        """Execute a full conversational response turn for the given user transcript."""
        generation_id = session.generation_controller.active_generation_id
        now_ns = time.perf_counter_ns()

        telemetry = TurnTelemetry(
            turn_id=turn_id,
            generation_id=generation_id,
            speech_start_ns=session.vad._speech_start_ts or now_ns,
            speech_end_ns=session.turn_detector._last_speech_end_ns or now_ns,
            asr_final_ns=now_ns,
        )
        session.current_turn_telemetry = telemetry

        # 1. State transition: Ensure session is in LISTENING before moving to THINKING
        if session.state_machine.current_state == VoiceState.IDLE:
            await session.state_machine.transition_to(
                VoiceState.LISTENING,
                reason="Turn started from IDLE"
            )

        if session.state_machine.can_transition_to(VoiceState.THINKING):
            await session.state_machine.transition_to(
                VoiceState.THINKING,
                reason=f"Processing Turn #{turn_id} transcript: '{user_text}'"
            )

        # 2. Fast Partial RAG Retrieval (<1ms in-memory lookup)
        matched_vehicles = catalog_service.search_from_user_text(user_text, limit=3)
        rag_context = catalog_service.format_rag_context(matched_vehicles)

        # Dynamic Partial Knowledge RAG (policies, warranties, financing, EV, test drive)
        matched_knowledge = await knowledge_engine.query(user_text, top_k=2)
        knowledge_context = knowledge_engine.format_retrieval_prompt(matched_knowledge)

        # 3. Build conversation context with Ground Truth & Session History
        history = conversation_history if conversation_history is not None else session.conversation_history
        messages = list(history)
        messages.append({"role": "user", "content": user_text})

        extra_context_parts = []
        if rag_context:
            extra_context_parts.append(rag_context)
        if knowledge_context:
            extra_context_parts.append(knowledge_context)
        rag_section = ("\n\n" + "\n\n".join(extra_context_parts)) if extra_context_parts else ""

        default_system_prompt = (
            system_prompt
            or (
                "You are Geeta, a friendly, professional automotive sales advisor at EchoDrive luxury dealership.\n\n"
                "CRITICAL VOICE CONVERSATION INSTRUCTIONS:\n"
                "1. CONCISE & SNAPPY: Keep your response short, crisp, and to the point in 1 to 2 natural sentences (around 20 to 30 words total). Do NOT speak long paragraphs.\n"
                "2. MANDATORY CLOSING SALES QUESTION: Every response MUST end with a short consultative sales question (e.g. asking which model they prefer, color choice, or offering a test drive).\n"
                "3. ACCURACY: Use ONLY authoritative specifications and prices from the catalog context below.\n"
                "4. NATURAL PRONUNCIATION: Speak prices naturally in Indian currency (e.g. '72.5 Lakh Rupees' or '1.14 Crore Rupees').\n"
                "5. SPOKEN DIALOGUE ONLY: NEVER output markdown tables, bullet points, asterisks, or pipe symbols (|).\n"
                "6. INTERRUPTION HANDLING: If the customer says a pause or interruption phrase ('wait', 'stop', 'hold on'), reply ONLY with 'Sure.' and nothing else.\n"
                + rag_section
            )
        )

        telemetry.llm_request_ns = time.perf_counter_ns()
        await session.event_bus.emit(
            LLMStarted(
                session_id=session.session_id,
                generation_id=generation_id,
                turn_id=turn_id,
                prompt=user_text,
                timestamp_ns=telemetry.llm_request_ns,
            )
        )

        is_first_token = True
        tts_tasks: List[asyncio.Task] = []
        generated_tokens: List[str] = []

        async def _synthesize_and_play(chunk_text: str, chunk_idx: int, is_final: bool) -> None:
            """Synthesizes a text chunk and streams audio frames to AudioOutputController."""
            if not session.generation_controller.is_valid(generation_id):
                logger.debug(f"[{session.session_id}] Skip TTS for stale gen={generation_id}")
                return

            req_ts = time.perf_counter_ns()
            if telemetry.tts_request_ns is None:
                telemetry.tts_request_ns = req_ts

            await session.event_bus.emit(
                TTSStarted(
                    session_id=session.session_id,
                    generation_id=generation_id,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    timestamp_ns=req_ts,
                )
            )

            if not session.tts_provider:
                return

            try:
                chunk_stream = session.tts_provider.synthesize_stream(
                    text=chunk_text,
                    generation_id=generation_id,
                    chunk_index=chunk_idx,
                    is_final=is_final,
                )
                async for audio_bytes in chunk_stream:
                    # Check validity before emitting audio
                    if not session.generation_controller.is_valid(generation_id):
                        logger.debug(f"[{session.session_id}] Discarding TTS frame for stale gen={generation_id}")
                        break

                    audio_ts = time.perf_counter_ns()
                    if telemetry.tts_first_audio_ns is None:
                        telemetry.tts_first_audio_ns = audio_ts

                    # State transition: THINKING -> SPEAKING on first audio chunk
                    if session.state_machine.is_thinking() and session.state_machine.can_transition_to(VoiceState.SPEAKING):
                        await session.state_machine.transition_to(
                            VoiceState.SPEAKING,
                            reason=f"Playback starting for Turn #{turn_id}"
                        )

                    # Send to explicit Audio Output Controller boundary
                    played = await session.audio_output.play_chunk_direct(
                        audio_data=audio_bytes,
                        generation_id=generation_id,
                        chunk_index=chunk_idx,
                        is_final=is_final,
                    )
                    if played and telemetry.first_audio_played_ns is None:
                        telemetry.first_audio_played_ns = audio_ts
            except asyncio.CancelledError:
                logger.debug(f"[{session.session_id}] TTS task cancelled for chunk #{chunk_idx}")
                raise
            except Exception as e:
                logger.error(f"[{session.session_id}] TTS synthesis error: {e}", exc_info=True)

        try:
            # 4. Stream LLM tokens (or fast-path pause phrase) and feed into progressive sentence chunker
            clean_user_text = re.sub(r"[^\w\s]", "", user_text.lower()).strip()
            if clean_user_text in PAUSE_PHRASES:
                async def _fast_pause_stream():
                    yield "Sure."
                token_stream = _fast_pause_stream()
            elif session.llm_provider:
                token_stream = session.llm_provider.stream_chat(
                    messages=messages,
                    system_prompt=default_system_prompt,
                    generation_id=generation_id,
                )
            else:
                token_stream = None

            if token_stream:
                async for token in token_stream:
                    # Validate generation ID during streaming
                    if not session.generation_controller.is_valid(generation_id):
                        logger.info(f"[{session.session_id}] LLM token stream aborted for obsolete gen={generation_id}")
                        break

                    now_token_ns = time.perf_counter_ns()
                    if is_first_token:
                        telemetry.llm_ttft_ns = now_token_ns
                        is_first_token = False

                    generated_tokens.append(token)

                    await session.event_bus.emit(
                        LLMToken(
                            session_id=session.session_id,
                            generation_id=generation_id,
                            delta=token,
                            is_first_token=is_first_token,
                            timestamp_ns=now_token_ns,
                        )
                    )

                    # Chunker extracts completed sentences / clauses
                    ready_chunks = session.chunker.process_token(token)
                    for c_text, c_idx, c_final in ready_chunks:
                        await session.event_bus.emit(
                            ChunkReady(
                                session_id=session.session_id,
                                generation_id=generation_id,
                                text=c_text,
                                chunk_index=c_idx,
                                is_final=c_final,
                            )
                        )
                        task = asyncio.create_task(_synthesize_and_play(c_text, c_idx, c_final))
                        session.cancellation.register_tts_task(task)
                        tts_tasks.append(task)

                # Mandatory Consultative Question Guarantee
                full_raw_text = "".join(generated_tokens).strip()
                if (
                    session.generation_controller.is_valid(generation_id)
                    and full_raw_text
                    and full_raw_text != "Sure."
                    and "?" not in full_raw_text
                ):
                    fallback_q = " Would you like to check out available colors or schedule a test drive?"
                    generated_tokens.append(fallback_q)
                    await session.event_bus.emit(
                        LLMToken(
                            session_id=session.session_id,
                            generation_id=generation_id,
                            delta=fallback_q,
                            is_first_token=False,
                            timestamp_ns=time.perf_counter_ns(),
                        )
                    )
                    ready_chunks = session.chunker.process_token(fallback_q)
                    for c_text, c_idx, c_final in ready_chunks:
                        await session.event_bus.emit(
                            ChunkReady(
                                session_id=session.session_id,
                                generation_id=generation_id,
                                text=c_text,
                                chunk_index=c_idx,
                                is_final=c_final,
                            )
                        )
                        task = asyncio.create_task(_synthesize_and_play(c_text, c_idx, c_final))
                        session.cancellation.register_tts_task(task)
                        tts_tasks.append(task)

                # Flush any remaining text in chunker
                final_chunks = session.chunker.flush()
                for c_text, c_idx, c_final in final_chunks:
                    await session.event_bus.emit(
                        ChunkReady(
                            session_id=session.session_id,
                            generation_id=generation_id,
                            text=c_text,
                            chunk_index=c_idx,
                            is_final=c_final,
                        )
                    )
                    task = asyncio.create_task(_synthesize_and_play(c_text, c_idx, True))
                    session.cancellation.register_tts_task(task)
                    tts_tasks.append(task)

            # Wait for all TTS chunks to finish playing
            if tts_tasks:
                await asyncio.gather(*tts_tasks, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info(f"[{session.session_id}] Pipeline turn execution cancelled")
            raise
        finally:
            telemetry.turn_complete_ns = time.perf_counter_ns()
            # If still speaking and turn wasn't interrupted, return to LISTENING
            if session.state_machine.is_speaking() and session.state_machine.can_transition_to(VoiceState.LISTENING):
                await session.state_machine.transition_to(
                    VoiceState.LISTENING,
                    reason=f"Turn #{turn_id} playback completed normally"
                )

            # Record telemetry and log trace
            session.metrics_collector.record_turn(telemetry)
            logger.info(telemetry.format_turn_trace())

            agent_full_text = "".join(generated_tokens)
            total_turn_ms = (telemetry.turn_complete_ns - (telemetry.speech_start_ns or now_ns)) / 1_000_000.0

            # Update multi-turn session conversation memory (bounded to last 12 entries)
            if agent_full_text.strip():
                session.conversation_history.append({"role": "user", "content": user_text})
                session.conversation_history.append({"role": "assistant", "content": agent_full_text.strip()})
                if len(session.conversation_history) > 12:
                    session.conversation_history = session.conversation_history[-12:]

            # 5. Async Non-blocking Persistence & CRM Lead Qualification
            async def _persist_turn_and_lead() -> None:
                try:
                    await persistence_repo.save_turn(
                        session_id=session.session_id,
                        turn_id=turn_id,
                        generation_id=generation_id,
                        user_text=user_text,
                        agent_text=agent_full_text,
                        ttfa_ms=telemetry.ttfa_ms or 0.0,
                        total_turn_ms=total_turn_ms,
                        interrupted=not session.generation_controller.is_valid(generation_id),
                    )
                    current_lead = await persistence_repo.get_lead(session.session_id)
                    updated_lead = LeadExtractor.extract_from_turn(
                        user_text=user_text,
                        current_lead=current_lead,
                        session_id=session.session_id,
                    )
                    await persistence_repo.upsert_lead(updated_lead)
                except Exception as ex:
                    logger.error(f"[{session.session_id}] Persistence error: {ex}", exc_info=True)

            persist_task = asyncio.create_task(_persist_turn_and_lead())
            session.register_task(persist_task)

            await session.event_bus.emit(
                TurnCompleted(
                    session_id=session.session_id,
                    turn_id=turn_id,
                    generation_id=generation_id,
                    ttfa_ms=telemetry.ttfa_ms or 0.0,
                    total_turn_ms=total_turn_ms,
                )
            )

        return telemetry
