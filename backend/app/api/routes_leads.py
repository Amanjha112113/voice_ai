"""FastAPI Endpoints for EchoDrive CRM Leads and Transcripts."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from ..persistence import persistence_repo, LeadStatus

router = APIRouter(prefix="/leads", tags=["CRM & Leads"])


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


@router.get("", response_model=List[dict])
async def list_leads(limit: int = Query(50, ge=1, le=100)):
    """List all qualified sales leads captured during customer conversations."""
    leads = await persistence_repo.list_leads(limit=limit)
    return [l.to_dict() for l in leads]


@router.get("/{session_id}")
async def get_lead_details(session_id: str):
    """Retrieve full lead details and session transcripts."""
    lead = await persistence_repo.get_lead(session_id)
    transcripts = await persistence_repo.get_transcripts(session_id)

    return {
        "session_id": session_id,
        "lead": lead.to_dict() if lead else None,
        "transcript_turns": [
            {
                "turn_id": t.turn_id,
                "generation_id": t.generation_id,
                "user_text": t.user_text,
                "agent_text": t.agent_text,
                "ttfa_ms": round(t.ttfa_ms, 1),
                "total_turn_ms": round(t.total_turn_ms, 1),
                "interrupted": t.interrupted,
                "timestamp": t.timestamp,
            }
            for t in transcripts
        ],
    }


@router.patch("/{session_id}/status")
async def update_lead_status(session_id: str, payload: LeadStatusUpdate):
    """Update qualification or booking status for a lead."""
    updated = await persistence_repo.update_lead_status(session_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Lead with session_id '{session_id}' not found")
    return updated.to_dict()
