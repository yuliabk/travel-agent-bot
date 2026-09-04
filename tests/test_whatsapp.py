"""Tests for the WhatsApp channel (src/channels/whatsapp.py).

Meta Cloud API calls and the agent core are mocked; no network I/O happens.
"""
import hashlib
import hmac
import json

import pytest

from src.core import config
from src.core.agent import AgentResponse


def _sign(raw: bytes) -> str:
    digest = hmac.new(config.WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _text_message_payload(from_phone="972501112222", text="Plan a trip to Rome", msg_id="wamid.TEST1"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": from_phone,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


# --- Webhook verification (GET) ---------------------------------------------

def test_verify_webhook_success(client):
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": config.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "challenge-12345",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge-12345"


def test_verify_webhook_wrong_token_returns_403(client):
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "x",
        },
    )
    assert resp.status_code == 403


def test_verify_webhook_wrong_mode_returns_403(client):
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": config.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "x",
        },
    )
    assert resp.status_code == 403


# --- Inbound message (POST) --------------------------------------------------

def test_receive_valid_message_dispatches_processing(client, monkeypatch):
    captured = {}

    def fake_process(sender_phone, msg_type, msg_data):
        captured["sender"] = sender_phone
        captured["type"] = msg_type
        captured["data"] = msg_data

    monkeypatch.setattr("src.channels.whatsapp.process_interaction", fake_process)

    raw = json.dumps(_text_message_payload()).encode()
    resp = client.post(
        "/webhook",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    # Background task runs after the response with TestClient.
    assert captured["sender"] == "972501112222"
    assert captured["type"] == "text"
    assert captured["data"]["text"]["body"] == "Plan a trip to Rome"


def test_receive_invalid_signature_returns_403(client, monkeypatch):
    called = {"count": 0}
    monkeypatch.setattr(
        "src.channels.whatsapp.process_interaction",
        lambda *a, **k: called.__setitem__("count", called["count"] + 1),
    )
    raw = json.dumps(_text_message_payload()).encode()
    resp = client.post(
        "/webhook",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    assert called["count"] == 0  # processing must not run


def test_receive_missing_signature_returns_403(client):
    raw = json.dumps(_text_message_payload()).encode()
    resp = client.post("/webhook", content=raw, headers={"Content-Type": "application/json"})
    assert resp.status_code == 403


def test_receive_non_message_event_is_ignored(client, monkeypatch):
    called = {"count": 0}
    monkeypatch.setattr(
        "src.channels.whatsapp.process_interaction",
        lambda *a, **k: called.__setitem__("count", called["count"] + 1),
    )
    raw = json.dumps({"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}).encode()
    resp = client.post(
        "/webhook",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert called["count"] == 0


# --- Signature helper --------------------------------------------------------

def test_verify_signature_function():
    from src.channels.whatsapp import verify_signature

    raw = b'{"hello":"world"}'
    assert verify_signature(raw, _sign(raw)) is True
    assert verify_signature(raw, "sha256=bad") is False
    assert verify_signature(raw, "") is False


# --- Background processing logic --------------------------------------------

def test_process_interaction_sends_reply_and_pdf(monkeypatch, agent_response):
    import src.channels.whatsapp as wa

    sent_texts = []
    sent_pdfs = []
    monkeypatch.setattr(wa, "mark_message_as_read", lambda mid: None)
    monkeypatch.setattr(wa, "send_whatsapp_text", lambda to, text: sent_texts.append((to, text)))
    monkeypatch.setattr(wa, "upload_and_send_pdf", lambda to, pdf, fn, cap: sent_pdfs.append((to, fn)))
    monkeypatch.setattr(wa.travel_agent, "handle_message", lambda *a, **k: agent_response)

    wa.process_interaction("972501112222", "text", {"id": "m1", "text": {"body": "Rome trip"}})

    # An immediate ack + the final summary text should have been sent.
    assert any("Rome, Italy" in t for _, t in sent_texts)
    assert sent_pdfs and sent_pdfs[0][1] == "Trip_Plan_Rome.pdf"


def test_process_interaction_empty_text_sends_fallback(monkeypatch):
    import src.channels.whatsapp as wa

    sent_texts = []
    handle_called = {"count": 0}
    monkeypatch.setattr(wa, "mark_message_as_read", lambda mid: None)
    monkeypatch.setattr(wa, "send_whatsapp_text", lambda to, text: sent_texts.append((to, text)))
    monkeypatch.setattr(
        wa.travel_agent, "handle_message",
        lambda *a, **k: handle_called.__setitem__("count", handle_called["count"] + 1),
    )

    wa.process_interaction("972501112222", "text", {"id": "m2", "text": {"body": "   "}})

    # No itinerary processing for an empty message; a clarifying reply is sent.
    assert handle_called["count"] == 0
    assert any("לא הצלחנו" in t for _, t in sent_texts)


def test_process_interaction_handoff_notifies_agent(monkeypatch):
    import src.channels.whatsapp as wa

    sent_texts = []
    monkeypatch.setattr(wa, "mark_message_as_read", lambda mid: None)
    monkeypatch.setattr(wa, "send_whatsapp_text", lambda to, text: sent_texts.append((to, text)))
    monkeypatch.setattr(wa, "upload_and_send_pdf", lambda *a, **k: None)
    handoff_resp = AgentResponse(text="הועברת לנציג", handoff=True, handoff_reason="בקשת נציג מפורשת")
    monkeypatch.setattr(wa.travel_agent, "handle_message", lambda *a, **k: handoff_resp)

    wa.process_interaction("972501112222", "text", {"id": "m3", "text": {"body": "נציג בבקשה"}})

    recipients = [to for to, _ in sent_texts]
    # The human agent number should receive a handoff alert.
    assert config.AGENT_PHONE_NUMBER in recipients
