"""Tests for the Web Form channel (POST /api/webform).

The agent core is mocked so no AI/network calls happen.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "name": "Dana Levi",
    "email": "dana@example.com",
    "phone": "+972500000000",
    "tripDetails": {
        "destination": "Rome, Italy",
        "dates": "10-17 August 2026",
        "budget": "1500 USD per person",
        "travelers": "2 adults + 1 child",
        "preferences": "kosher food, relaxed pace, art museums",
    },
}


@pytest.fixture
def patch_agent(monkeypatch, agent_response):
    """Patch the shared agent so the endpoint returns a canned response."""
    captured = {}

    def fake_handle(channel, user_id, message, context=None):
        captured["channel"] = channel
        captured["user_id"] = user_id
        captured["message"] = message
        captured["context"] = context
        return agent_response

    monkeypatch.setattr("src.channels.webform.travel_agent.handle_message", fake_handle)
    return captured


# --- Happy path --------------------------------------------------------------


def test_webform_valid_returns_200_with_ai_reply(client, patch_agent):
    resp = client.post("/api/webform", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["destination"] == "Rome, Italy"
    assert "Rome, Italy" in body["message"]
    assert body["pdf_base64"] is not None  # PDF was encoded
    assert body["handoff"] is False
    assert body["email_sent"] is False  # WEBFORM_SEND_EMAIL_REPLY is off


def test_webform_uses_email_as_user_id_and_builds_brief(client, patch_agent):
    client.post("/api/webform", json=VALID_PAYLOAD)
    assert patch_agent["channel"] == "webform"
    assert patch_agent["user_id"] == "dana@example.com"
    # The natural-language brief must contain the structured details.
    assert "Rome, Italy" in patch_agent["message"]
    assert "Dana Levi" in patch_agent["message"]


def test_webform_minimal_payload_only_required_fields(client, patch_agent):
    payload = {"name": "Bob", "tripDetails": {"destination": "Paris"}}
    resp = client.post("/api/webform", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Without email/phone, the user id falls back to the name.
    assert patch_agent["user_id"] == "Bob"


# --- Validation (422) --------------------------------------------------------


def test_webform_missing_name_returns_422(client, patch_agent):
    payload = {"email": "x@y.com", "tripDetails": {"destination": "Rome"}}
    resp = client.post("/api/webform", json=payload)
    assert resp.status_code == 422


def test_webform_missing_destination_returns_422(client, patch_agent):
    payload = {"name": "Dana", "tripDetails": {}}
    resp = client.post("/api/webform", json=payload)
    assert resp.status_code == 422


def test_webform_missing_tripdetails_returns_422(client, patch_agent):
    resp = client.post("/api/webform", json={"name": "Dana"})
    assert resp.status_code == 422


def test_webform_invalid_email_returns_422(client, patch_agent):
    payload = {"name": "Dana", "email": "not-an-email", "tripDetails": {"destination": "Rome"}}
    resp = client.post("/api/webform", json=payload)
    assert resp.status_code == 422


def test_webform_too_short_destination_returns_422(client, patch_agent):
    payload = {"name": "Dana", "tripDetails": {"destination": "R"}}
    resp = client.post("/api/webform", json=payload)
    assert resp.status_code == 422


# --- Rate limiting -----------------------------------------------------------


def test_webform_rate_limiting_returns_429(monkeypatch, agent_response):
    """Rebuild the app with a low web-form limit and confirm the 4th call 429s.

    We reload config -> rate_limit -> channels -> main so the ``@limiter.limit``
    decorator picks up the low limit, then restore the modules afterwards.
    """
    import os

    orig_webform = os.environ.get("RATE_LIMIT_WEBFORM")
    os.environ["RATE_LIMIT_WEBFORM"] = "3/minute"
    try:
        from src.core import config as cfg

        importlib.reload(cfg)
        from src.core import rate_limit as rl

        importlib.reload(rl)
        from src.channels import webform as wf

        importlib.reload(wf)
        import main as m

        importlib.reload(m)

        monkeypatch.setattr(
            "src.channels.webform.travel_agent.handle_message",
            lambda channel, user_id, message, context=None: agent_response,
        )

        with TestClient(m.app) as c:
            codes = [c.post("/api/webform", json=VALID_PAYLOAD).status_code for _ in range(4)]

        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
    finally:
        # Restore the original environment and module state for other tests.
        if orig_webform is None:
            os.environ.pop("RATE_LIMIT_WEBFORM", None)
        else:
            os.environ["RATE_LIMIT_WEBFORM"] = orig_webform
        from src.core import config as cfg

        importlib.reload(cfg)
        from src.core import rate_limit as rl

        importlib.reload(rl)
        from src.channels import webform as wf

        importlib.reload(wf)
        import main as m

        importlib.reload(m)
