"""Tests for the unified agent core (src/core/agent.py).

All Google Gemini and SerpApi calls are mocked; no network I/O happens.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from pydantic_models import (
    ClientTravelRequirements,
    TripOverview,
    Travelers,
)
from src.core import agent as agent_mod
from src.core.agent import TravelAgent, AgentResponse


@pytest.fixture
def req_stub() -> ClientTravelRequirements:
    start = date.today() + timedelta(days=30)
    return ClientTravelRequirements(
        trip_overview=TripOverview(
            destination="Rome, Italy",
            start_date=start,
            end_date=start + timedelta(days=3),
        ),
        travelers=Travelers(adults_count=2),
    )


@pytest.fixture
def mocked_agent(monkeypatch, sample_itinerary, req_stub):
    """A TravelAgent whose AI + travel tools are fully mocked."""
    ta = TravelAgent()
    # Pretend the Gemini client is available.
    ta._ai_client = MagicMock(name="gemini_client")

    monkeypatch.setattr(ta, "extract_requirements", lambda text: req_stub)
    monkeypatch.setattr(ta, "build_itinerary", lambda req: sample_itinerary)
    monkeypatch.setattr(ta, "update_itinerary", lambda cur, fb: sample_itinerary)
    # No explicit handoff by default.
    monkeypatch.setattr(ta, "check_human_handoff", lambda text: (False, ""))

    # Mock external travel tools.
    monkeypatch.setattr(agent_mod.travel_tools, "get_iata_code", lambda c, d: "FCO")
    monkeypatch.setattr(
        agent_mod.travel_tools,
        "search_flights_google",
        lambda **kw: [
            {"airline": "ELAL", "price": "$500", "departure_time": "", "arrival_time": "", "type": "טיסה ישירה"}
        ],
    )
    monkeypatch.setattr(
        agent_mod.travel_tools,
        "search_hotels_google",
        lambda **kw: [
            {
                "name": "Hotel Roma",
                "stars": "",
                "rating": "",
                "lowest_price": "120",
                "booking_price": None,
                "agoda_price": None,
            }
        ],
    )
    monkeypatch.setattr(
        agent_mod.travel_tools, "build_pdf_document", lambda it, f, h: __import__("io").BytesIO(b"%PDF fake")
    )
    return ta


# --- Basic response ----------------------------------------------------------


def test_handle_message_basic_response(mocked_agent):
    resp = mocked_agent.handle_message("whatsapp", "user-1", "Trip to Rome next month for 2")
    assert isinstance(resp, AgentResponse)
    assert resp.error is False
    assert resp.destination == "Rome, Italy"
    assert resp.pdf_bytes is not None
    assert resp.pdf_filename == "Trip_Plan_Rome, Italy.pdf"
    assert "Rome, Italy" in resp.text
    assert resp.meta["flights"] == 1
    assert resp.meta["hotels"] == 1


def test_handle_message_empty_message_is_error(mocked_agent):
    resp = mocked_agent.handle_message("whatsapp", "user-1", "   ")
    assert resp.error is True
    assert resp.pdf_bytes is None


def test_handle_message_without_ai_client_returns_error(monkeypatch):
    ta = TravelAgent()
    ta._ai_client = None
    resp = ta.handle_message("whatsapp", "u", "hello")
    assert resp.error is True
    assert "זמין" in resp.text or "AI" in resp.text


# --- Session history management ---------------------------------------------


def test_handle_message_records_history(mocked_agent):
    from src.core.session import session_manager

    mocked_agent.handle_message("email", "dana@example.com", "Plan Rome trip")
    session = session_manager.get("email", "dana@example.com")
    roles = [h["role"] for h in session["history"]]
    assert "user" in roles
    assert "assistant" in roles
    assert session["current_itinerary"] is not None


def test_second_message_updates_existing_itinerary(mocked_agent, monkeypatch):
    from src.core.session import session_manager

    # First message builds the itinerary.
    mocked_agent.handle_message("whatsapp", "u2", "Plan Rome")
    # extract_requirements must NOT be used on the second turn.
    monkeypatch.setattr(
        mocked_agent,
        "extract_requirements",
        lambda text: (_ for _ in ()).throw(AssertionError("extract should not run on update")),
    )
    resp = mocked_agent.handle_message("whatsapp", "u2", "Add a food tour on day 1")
    assert resp.error is False
    assert resp.destination == "Rome, Italy"
    session = session_manager.get("whatsapp", "u2")
    assert session["current_itinerary"] is not None


# --- Triage / human handoff --------------------------------------------------


def test_explicit_keyword_triggers_handoff(mocked_agent, monkeypatch):
    # Use the real triage logic (the fixture stubs it out by default).
    monkeypatch.setattr(
        mocked_agent,
        "check_human_handoff",
        lambda text: TravelAgent.check_human_handoff(mocked_agent, text),
    )
    resp = mocked_agent.handle_message("whatsapp", "angry", "אני רוצה לדבר עם נציג אנושי")
    assert resp.handoff is True
    assert resp.handoff_reason  # non-empty reason
    from src.core.session import session_manager

    session = session_manager.get("whatsapp", "angry")
    assert session["is_human_takeover"] is True


def test_check_human_handoff_explicit_keywords_direct():
    ta = TravelAgent()
    needs, reason = ta.check_human_handoff("תעביר אותי לשירות לקוחות")
    assert needs is True
    assert reason


def test_check_human_handoff_no_keyword_no_ai_returns_false():
    ta = TravelAgent()
    ta._ai_client = None  # no AI available
    needs, reason = ta.check_human_handoff("I want to visit Rome")
    assert needs is False


def test_human_takeover_suppresses_further_replies(mocked_agent):
    from src.core.session import session_manager

    # Force takeover state.
    s = session_manager.get("whatsapp", "u3")
    s["is_human_takeover"] = True
    session_manager.save("whatsapp", "u3", s)

    resp = mocked_agent.handle_message("whatsapp", "u3", "still talking")
    assert resp.text == ""
    assert resp.meta.get("suppressed") is True
