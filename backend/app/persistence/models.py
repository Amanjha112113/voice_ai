"""Persistence and Lead CRM Data Models for EchoDrive."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any


class LeadStatus(str, Enum):
    NEW = "NEW"
    EXPLORING = "EXPLORING"
    QUALIFIED = "QUALIFIED"
    TEST_DRIVE_REQUESTED = "TEST_DRIVE_REQUESTED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    ESCALATED_HUMAN = "ESCALATED_HUMAN"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


@dataclass
class TranscriptTurnRecord:
    """Individual conversational turn stored persistently."""
    session_id: str
    turn_id: int
    generation_id: str
    user_text: str
    agent_text: str
    ttfa_ms: float
    total_turn_ms: float
    interrupted: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LeadRecord:
    """Structured CRM Lead captured during conversation."""
    session_id: str
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    budget_max_inr: Optional[int] = None
    budget_display: Optional[str] = None
    preferred_make: Optional[str] = None
    preferred_model: Optional[str] = None
    preferred_body_type: Optional[str] = None
    preferred_fuel: Optional[str] = None
    purchase_timeline: Optional[str] = None
    test_drive_requested: bool = False
    appointment_slot: Optional[str] = None
    status: LeadStatus = LeadStatus.NEW
    notes: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "customer_name": self.customer_name,
            "phone_number": self.phone_number,
            "email": self.email,
            "budget_max_inr": self.budget_max_inr,
            "budget_display": self.budget_display,
            "preferred_make": self.preferred_make,
            "preferred_model": self.preferred_model,
            "preferred_body_type": self.preferred_body_type,
            "preferred_fuel": self.preferred_fuel,
            "purchase_timeline": self.purchase_timeline,
            "test_drive_requested": self.test_drive_requested,
            "appointment_slot": self.appointment_slot,
            "status": self.status.value,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
