"""Lead Extraction Engine for EchoDrive.

Extracts structured customer preferences, budget, contact information,
and booking intents from real-time conversation turns.
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from .models import LeadRecord, LeadStatus

# Common car brands to detect
KNOWN_MAKES = {
    "mercedes": "Mercedes-Benz",
    "mercedes-benz": "Mercedes-Benz",
    "benz": "Mercedes-Benz",
    "bmw": "BMW",
    "audi": "Audi",
    "mahindra": "Mahindra",
    "tata": "Tata",
    "hyundai": "Hyundai",
    "kia": "Kia",
    "toyota": "Toyota",
    "porsche": "Porsche",
}

# Known models
KNOWN_MODELS = {
    "c-class": ("Mercedes-Benz", "C-Class"),
    "e-class": ("Mercedes-Benz", "E-Class"),
    "glc": ("Mercedes-Benz", "GLC"),
    "s-class": ("Mercedes-Benz", "S-Class"),
    "3 series": ("BMW", "3 Series Gran Limousine"),
    "x5": ("BMW", "X5"),
    "a6": ("Audi", "A6"),
    "q7": ("Audi", "Q7"),
    "xuv700": ("Mahindra", "XUV700"),
    "scorpio": ("Mahindra", "Scorpio-N"),
    "scorpio-n": ("Mahindra", "Scorpio-N"),
    "safari": ("Tata", "Safari"),
    "harrier": ("Tata", "Harrier"),
    "ioniq 5": ("Hyundai", "Ioniq 5"),
    "creta": ("Hyundai", "Creta"),
}


class LeadExtractor:
    """Extracts lead details incrementally as conversation progresses."""

    @staticmethod
    def extract_from_turn(
        user_text: str,
        current_lead: Optional[LeadRecord] = None,
        session_id: str = "default_session"
    ) -> LeadRecord:
        """Analyze user text and update or create lead record."""
        lead = current_lead or LeadRecord(session_id=session_id)
        text_lower = user_text.lower()

        # 1. Extract Make / Model
        for model_key, (make, model_name) in KNOWN_MODELS.items():
            if model_key in text_lower:
                lead.preferred_make = make
                lead.preferred_model = model_name
                lead.notes.append(f"Expressed interest in {make} {model_name}")
                break

        if not lead.preferred_make:
            for make_key, make_val in KNOWN_MAKES.items():
                if make_key in text_lower:
                    lead.preferred_make = make_val
                    lead.notes.append(f"Expressed interest in {make_val}")
                    break

        # 2. Extract Body Type
        if "suv" in text_lower or "4x4" in text_lower:
            lead.preferred_body_type = "SUV"
        elif "sedan" in text_lower or "limousine" in text_lower:
            lead.preferred_body_type = "Sedan"
        elif "coupe" in text_lower:
            lead.preferred_body_type = "Coupe"

        # 3. Extract Fuel Preference
        if "ev" in text_lower or "electric" in text_lower:
            lead.preferred_fuel = "Electric"
        elif "diesel" in text_lower:
            lead.preferred_fuel = "Diesel"
        elif "petrol" in text_lower or "gasoline" in text_lower:
            lead.preferred_fuel = "Petrol"
        elif "hybrid" in text_lower:
            lead.preferred_fuel = "Hybrid"

        # 4. Extract Budget
        cr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr|crore|crores)", text_lower)
        if cr_match:
            cr_val = float(cr_match.group(1))
            lead.budget_max_inr = int(cr_val * 10_000_000)
            lead.budget_display = f"₹{cr_val} Crore"
            lead.notes.append(f"Budget indicated: {lead.budget_display}")

        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|l|lac|lacs)", text_lower)
        if lakh_match and not cr_match:
            lakh_val = float(lakh_match.group(1))
            lead.budget_max_inr = int(lakh_val * 100_000)
            lead.budget_display = f"₹{lakh_val} Lakh"
            lead.notes.append(f"Budget indicated: {lead.budget_display}")

        # 5. Extract Phone Number (Indian 10-digit formats)
        phone_match = re.search(r"(?:(?:\+91|0)?[ -]?)?([6-9]\d{9})", user_text)
        if phone_match:
            lead.phone_number = phone_match.group(1)
            lead.notes.append(f"Provided contact number: {lead.phone_number}")

        # 6. Extract Email
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", user_text)
        if email_match:
            lead.email = email_match.group(0)
            lead.notes.append(f"Provided email: {lead.email}")

        # 7. Extract Name if phrased like "I am [Name]", "My name is [Name]", "This is [Name]"
        STOP_WORDS = {
            "looking", "exploring", "interested", "planning", "wondering",
            "searching", "trying", "hoping", "ready", "checking", "asking",
            "calling", "thinking", "wanting", "just", "here", "fine", "good"
        }
        name_match = re.search(r"(?:my name is|this is|i am|i'm)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)", user_text, re.IGNORECASE)
        if name_match:
            candidate_words = name_match.group(1).strip().split()
            first_word_lower = candidate_words[0].lower() if candidate_words else ""
            if first_word_lower not in STOP_WORDS:
                lead.customer_name = " ".join(candidate_words).title()

        # 8. Test Drive / Appointment Booking Detection
        if any(kw in text_lower for kw in [
            "test drive", "test-drive", "book a slot", "book an appointment",
            "visit showroom", "come over tomorrow", "schedule a drive",
            "book that", "book upcoming", "book for", "book on", "schedule for",
            "reserve a slot", "reserve a unit", "confirm booking"
        ]):
            lead.test_drive_requested = True
            lead.status = LeadStatus.TEST_DRIVE_REQUESTED
            lead.notes.append(f"Customer requested appointment: '{user_text.strip()}'")

        # 9. Update Qualification Status
        if lead.status not in [LeadStatus.TEST_DRIVE_REQUESTED, LeadStatus.APPOINTMENT_BOOKED]:
            if lead.budget_max_inr and (lead.preferred_make or lead.preferred_model):
                lead.status = LeadStatus.QUALIFIED
            elif lead.preferred_make or lead.preferred_body_type or lead.budget_max_inr:
                lead.status = LeadStatus.EXPLORING

        lead.updated_at = datetime.now(timezone.utc).isoformat()
        return lead
