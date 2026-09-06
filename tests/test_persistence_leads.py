"""Unit Tests for EchoDrive Persistence and Lead Extraction Engine."""

import pytest
from backend.app.persistence.models import LeadStatus, LeadRecord
from backend.app.persistence.lead_extractor import LeadExtractor
from backend.app.persistence.storage import PersistenceRepository


def test_lead_extractor_budget_and_model():
    user_text = "Hi, my name is Rohit. I am looking for a Mercedes E-Class and my budget is 90 Lakhs."
    lead = LeadExtractor.extract_from_turn(user_text, session_id="test_sess_01")

    assert lead.customer_name == "Rohit"
    assert lead.preferred_make == "Mercedes-Benz"
    assert lead.preferred_model == "E-Class"
    assert lead.budget_max_inr == 9000000
    assert lead.status in [LeadStatus.QUALIFIED, LeadStatus.EXPLORING]


def test_lead_extractor_test_drive_and_phone():
    user_text = "Can I schedule a test drive for tomorrow? My phone number is 9876543210."
    lead = LeadExtractor.extract_from_turn(user_text, session_id="test_sess_02")

    assert lead.test_drive_requested is True
    assert lead.phone_number == "9876543210"
    assert lead.status == LeadStatus.TEST_DRIVE_REQUESTED


def test_lead_extractor_incremental_updates():
    # Turn 1
    lead1 = LeadExtractor.extract_from_turn("I want a 7-seater diesel SUV", session_id="test_sess_03")
    assert lead1.preferred_body_type == "SUV"
    assert lead1.preferred_fuel == "Diesel"

    # Turn 2 (with previous lead)
    lead2 = LeadExtractor.extract_from_turn("I like the Mahindra XUV700 around 30 Lakhs", current_lead=lead1, session_id="test_sess_03")
    assert lead2.preferred_make == "Mahindra"
    assert lead2.preferred_model == "XUV700"
    assert lead2.budget_max_inr == 3000000
    assert lead2.preferred_body_type == "SUV"  # Preserved from Turn 1


@pytest.mark.asyncio
async def test_persistence_repository_turns_and_leads():
    repo = PersistenceRepository()

    # Save turn
    saved_turn = await repo.save_turn(
        session_id="sess_abc",
        turn_id=1,
        generation_id="gen_xyz",
        user_text="What is the price of Mercedes C-Class?",
        agent_text="The Mercedes C-Class starts at ₹61.85 Lakhs ex-showroom.",
        ttfa_ms=450.0,
        total_turn_ms=1200.0,
        interrupted=False,
    )
    assert saved_turn.session_id == "sess_abc"

    # Retrieve transcripts
    transcripts = await repo.get_transcripts("sess_abc")
    assert len(transcripts) == 1
    assert transcripts[0].ttfa_ms == 450.0

    # Upsert and query lead
    lead = LeadRecord(
        session_id="sess_abc",
        customer_name="Aman",
        preferred_make="Mercedes-Benz",
        status=LeadStatus.QUALIFIED,
    )
    await repo.upsert_lead(lead)

    fetched_lead = await repo.get_lead("sess_abc")
    assert fetched_lead is not None
    assert fetched_lead.customer_name == "Aman"

    # Update status
    updated = await repo.update_lead_status("sess_abc", LeadStatus.TEST_DRIVE_REQUESTED)
    assert updated.status == LeadStatus.TEST_DRIVE_REQUESTED


def test_lead_extractor_booking_intent_variations():
    booking_phrases = [
        "yeah okay just book that upcoming Monday",
        "book that for next weekend",
        "schedule for tomorrow afternoon",
        "reserve a slot at the dealership",
    ]
    for phrase in booking_phrases:
        lead = LeadExtractor.extract_from_turn(phrase, session_id="test_booking")
        assert lead.test_drive_requested is True
        assert lead.status == LeadStatus.TEST_DRIVE_REQUESTED


@pytest.mark.asyncio
async def test_multi_turn_session_memory():
    from backend.app.voice.session import VoiceSession
    from backend.app.voice.pipeline import VoicePipeline
    from backend.app.providers.mock_providers import MockASRProvider, MockLLMProvider, MockTTSProvider

    session = VoiceSession(
        session_id="test_memory_sess",
        asr_provider=MockASRProvider(),
        llm_provider=MockLLMProvider(),
        tts_provider=MockTTSProvider(),
    )

    # Turn 1
    await VoicePipeline.process_user_turn(session, "I want a Mercedes GLC", turn_id=1)
    assert len(session.conversation_history) == 2
    assert session.conversation_history[0]["role"] == "user"
    assert session.conversation_history[0]["content"] == "I want a Mercedes GLC"

    # Turn 2
    await VoicePipeline.process_user_turn(session, "just book that upcoming Monday", turn_id=2)
    assert len(session.conversation_history) == 4
    assert session.conversation_history[2]["content"] == "just book that upcoming Monday"

