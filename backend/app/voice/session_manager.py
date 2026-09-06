"""Session Manager for EchoDrive.

Central registry managing active voice sessions, lifetime policies,
and Agora RTC room/token provisioning.
"""

import uuid
from typing import Dict, List, Optional
import asyncio
import logging

from .session import VoiceSession
from ..providers.agora_rtc import AgoraRTCGateway
from ..providers.base import ASRProvider, LLMProvider, TTSProvider, RTCGateway

logger = logging.getLogger(__name__)


class SessionManager:
    """Async registry managing lifetime of all VoiceSession instances."""

    def __init__(self, rtc_gateway: Optional[RTCGateway] = None) -> None:
        self._sessions: Dict[str, VoiceSession] = {}
        self.rtc_gateway = rtc_gateway or AgoraRTCGateway()
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        customer_id: Optional[str] = None,
        language: str = "en-IN",
        asr_provider: Optional[ASRProvider] = None,
        llm_provider: Optional[LLMProvider] = None,
        tts_provider: Optional[TTSProvider] = None,
    ) -> VoiceSession:
        """Create and register a new active voice session with Agora credentials."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        channel_name = f"echodrive_{session_id[:8]}"
        
        # Generate official Agora RTC channel access token
        agora_token = self.rtc_gateway.generate_token(
            channel_name=channel_name,
            uid=0,
            expire_seconds=3600,
        )

        if llm_provider is None:
            from ..providers.groq_llm import GroqLLMProvider
            llm_provider = GroqLLMProvider()

        session = VoiceSession(
            session_id=session_id,
            customer_id=customer_id,
            agora_channel=channel_name,
            agora_token=agora_token,
            language=language,
            asr_provider=asr_provider,
            llm_provider=llm_provider,
            tts_provider=tts_provider,
            rtc_gateway=self.rtc_gateway,
        )

        async with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created VoiceSession {session_id} in channel '{channel_name}'")
        return session

    async def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Retrieve active session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def list_sessions(self) -> List[VoiceSession]:
        """List all currently active sessions."""
        async with self._lock:
            return list(self._sessions.values())

    async def delete_session(self, session_id: str) -> bool:
        """Terminate and remove session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if session:
            await session.close()
            logger.info(f"Terminated VoiceSession {session_id}")
            return True
        return False


# Global singleton instance for the application
session_manager = SessionManager()
