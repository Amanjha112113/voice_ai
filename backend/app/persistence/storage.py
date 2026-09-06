"""Storage and Repository for EchoDrive Transcripts and CRM Leads.

Provides thread-safe async persistence for session history and sales leads.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
from .models import LeadRecord, TranscriptTurnRecord, LeadStatus

logger = logging.getLogger(__name__)


class PersistenceRepository:
    """Async repository for saving turn transcripts and leads."""

    def __init__(self):
        self._leads: Dict[str, LeadRecord] = {}  # session_id -> LeadRecord
        self._transcripts: Dict[str, List[TranscriptTurnRecord]] = {}  # session_id -> list of turns
        self._lock = asyncio.Lock()

    async def save_turn(
        self,
        session_id: str,
        turn_id: int,
        generation_id: str,
        user_text: str,
        agent_text: str,
        ttfa_ms: float,
        total_turn_ms: float,
        interrupted: bool = False,
    ) -> TranscriptTurnRecord:
        """Store completed turn transcript."""
        record = TranscriptTurnRecord(
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            user_text=user_text,
            agent_text=agent_text,
            ttfa_ms=ttfa_ms,
            total_turn_ms=total_turn_ms,
            interrupted=interrupted,
        )
        async with self._lock:
            if session_id not in self._transcripts:
                self._transcripts[session_id] = []
            self._transcripts[session_id].append(record)

        logger.info(f"[{session_id}] Persisted Turn #{turn_id} transcript (TTFA: {ttfa_ms:.1f}ms)")
        return record

    async def get_transcripts(self, session_id: str) -> List[TranscriptTurnRecord]:
        """Retrieve full transcript for session."""
        async with self._lock:
            return list(self._transcripts.get(session_id, []))

    async def upsert_lead(self, lead: LeadRecord) -> LeadRecord:
        """Save or update structured lead record."""
        async with self._lock:
            self._leads[lead.session_id] = lead
        logger.info(f"[{lead.session_id}] Lead updated: Status={lead.status.value}, Budget={lead.budget_display}, Make={lead.preferred_make}")
        return lead

    async def get_lead(self, session_id: str) -> Optional[LeadRecord]:
        """Retrieve lead for session."""
        async with self._lock:
            return self._leads.get(session_id)

    async def list_leads(self, limit: int = 50) -> List[LeadRecord]:
        """List all captured leads sorted by updated_at descending."""
        async with self._lock:
            leads = list(self._leads.values())
        leads.sort(key=lambda l: l.updated_at, reverse=True)
        return leads[:limit]

    async def update_lead_status(self, session_id: str, new_status: LeadStatus) -> Optional[LeadRecord]:
        """Update status of an existing lead."""
        async with self._lock:
            lead = self._leads.get(session_id)
            if lead:
                lead.status = new_status
                lead.updated_at = datetime.now(timezone.utc).isoformat()
                return lead
        return None


# Global repository instance
persistence_repo = PersistenceRepository()
