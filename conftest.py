"""
Shared pytest configuration and fixtures for the travel-agent-bot test suite.

Environment variables are set **before** any application module is imported so
that ``src.core.config`` (which reads ``os.environ`` at import time) picks up
deterministic test values. All external services (Google Gemini, SerpApi, Meta
WhatsApp API, IMAP/SMTP) are mocked in the individual test modules; nothing here
performs real network I/O.
"""
import io
import os

# --- Deterministic test environment (must run before app imports) -----------
os.environ.setdefault("GEMINI_API_KEY", "")          # keep AI client uninitialised
os.environ.setdefault("SERPAPI_API_KEY", "")         # skip real flight/hotel calls
os.environ.pop("REDIS_URL", None)                    # force in-memory session store
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token"
os.environ["WHATSAPP_APP_SECRET"] = "test_app_secret"
os.environ["AGENT_PHONE_NUMBER"] = "972500000000"
os.environ["SESSION_TTL_SECONDS"] = "3600"
os.environ["MAX_HISTORY_MESSAGES"] = "6"
os.environ["RATE_LIMIT_WEBHOOK"] = "1000/minute"
os.environ["RATE_LIMIT_WEBFORM"] = "1000/minute"
os.environ["LOG_DIR"] = "/tmp/travel_agent_test_logs"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pydantic_models import (  # noqa: E402
    TripItinerary,
    DayItinerary,
)
from src.core.agent import AgentResponse  # noqa: E402


# --- Sample domain objects ---------------------------------------------------

@pytest.fixture
def sample_itinerary() -> TripItinerary:
    """A minimal but valid TripItinerary used across tests."""
    return TripItinerary(
        destination="Rome, Italy",
        total_days=1,
        currency="USD",
        days=[
            DayItinerary(
                day_number=1,
                title="Ancient Rome",
                origin="Colosseum",
                stops=["Roman Forum"],
                destination="Pantheon",
                travel_mode="walking",
                daily_cost_estimate=90.0,
                summary="A walk through ancient Rome.",
                maps_url="https://maps.example/1",
            )
        ],
    )


@pytest.fixture
def sample_pdf_bytes() -> io.BytesIO:
    """A fake PDF buffer (content is irrelevant for the tests)."""
    buf = io.BytesIO(b"%PDF-1.4 fake pdf content")
    buf.seek(0)
    return buf


@pytest.fixture
def agent_response(sample_pdf_bytes) -> AgentResponse:
    """A canned successful AgentResponse."""
    return AgentResponse(
        text="✈️ תוכנית הטיול שלך ל-Rome, Italy מוכנה!",
        pdf_bytes=sample_pdf_bytes,
        pdf_filename="Trip_Plan_Rome.pdf",
        destination="Rome, Italy",
        meta={"flights": 2, "hotels": 3},
    )


# --- App / client fixtures ---------------------------------------------------

@pytest.fixture
def app():
    """The FastAPI application instance (imported lazily after env setup)."""
    import main
    return main.app


@pytest.fixture
def client(app):
    """A FastAPI TestClient. ``startup``/``shutdown`` events are exercised."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_sessions():
    """Ensure every test starts with a clean in-memory session store."""
    from src.core.session import session_manager

    backend = session_manager._backend
    if hasattr(backend, "_data"):
        backend._data.clear()
    if hasattr(backend, "_expiry"):
        backend._expiry.clear()
    yield
    if hasattr(backend, "_data"):
        backend._data.clear()
    if hasattr(backend, "_expiry"):
        backend._expiry.clear()
