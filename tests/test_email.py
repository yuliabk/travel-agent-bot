"""Tests for the Email channel (src/channels/email.py).

IMAP and SMTP are fully mocked; no network I/O or real mailboxes are touched.
"""
import io
from email.message import EmailMessage
from email.header import Header
from unittest.mock import MagicMock

import pytest

import src.channels.email as email_mod
from src.core.agent import AgentResponse


# --- Inbound parsing ---------------------------------------------------------

def _plain_email(from_addr="client@example.com", subject="Trip request", body="Plan me a trip to Rome"):
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg["To"] = "agent@example.com"
    msg.set_content(body)
    return msg


def test_extract_body_plain_text():
    msg = _plain_email(body="I want to visit Paris in May")
    assert "Paris" in email_mod._extract_body(msg)


def test_extract_body_multipart_prefers_plaintext():
    msg = EmailMessage()
    msg["From"] = "a@b.com"
    msg["Subject"] = "hi"
    msg.set_content("PLAINTEXT BODY")
    msg.add_alternative("<html><body>HTML BODY</body></html>", subtype="html")
    body = email_mod._extract_body(msg)
    assert "PLAINTEXT BODY" in body


def test_extract_body_html_only_is_stripped():
    # A multipart message whose only part is text/html -> tags are stripped.
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["From"] = "a@b.com"
    msg["Subject"] = "hi"
    msg.attach(MIMEText("<html><body>Hello <b>Rome</b></body></html>", "html"))
    body = email_mod._extract_body(msg)
    assert "Rome" in body
    assert "<b>" not in body


def test_decode_encoded_header():
    encoded = str(Header("שלום", "utf-8"))
    assert email_mod._decode(encoded) == "שלום"


def test_decode_empty_returns_empty():
    assert email_mod._decode(None) == ""


# --- Outbound reply building -------------------------------------------------

@pytest.fixture
def smtp_config(monkeypatch):
    monkeypatch.setattr(email_mod.config, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(email_mod.config, "SMTP_PORT", 587)
    monkeypatch.setattr(email_mod.config, "SMTP_USER", "user@test")
    monkeypatch.setattr(email_mod.config, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(email_mod.config, "SMTP_FROM", "from@test")
    monkeypatch.setattr(email_mod.config, "SMTP_USE_TLS", True)


def test_send_email_reply_builds_and_sends(monkeypatch, smtp_config):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, pwd):
            sent["login"] = (user, pwd)

        def send_message(self, msg):
            sent["msg"] = msg

    monkeypatch.setattr(email_mod.smtplib, "SMTP", FakeSMTP)

    ok = email_mod.send_email_reply(
        to_addr="client@example.com",
        subject="Re: Trip request",
        body="Here is your plan",
        pdf_bytes=io.BytesIO(b"%PDF fake"),
        pdf_filename="Trip_Plan.pdf",
    )
    assert ok is True
    assert sent["host"] == "smtp.test"
    assert sent["tls"] is True
    assert sent["login"] == ("user@test", "secret")
    msg = sent["msg"]
    assert msg["To"] == "client@example.com"
    assert msg["Subject"] == "Re: Trip request"
    assert msg["From"] == "from@test"
    # PDF attachment present.
    attachments = [p for p in msg.iter_attachments()]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "Trip_Plan.pdf"


def test_send_email_reply_no_smtp_config_returns_false(monkeypatch):
    monkeypatch.setattr(email_mod.config, "SMTP_HOST", "")
    monkeypatch.setattr(email_mod.config, "SMTP_USER", "")
    ok = email_mod.send_email_reply("x@y.com", "subj", "body")
    assert ok is False


def test_send_email_reply_smtp_failure_returns_false(monkeypatch, smtp_config):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(email_mod.smtplib, "SMTP", boom)
    ok = email_mod.send_email_reply("x@y.com", "subj", "body")
    assert ok is False


# --- End-to-end inbound processing ------------------------------------------

def test_process_email_replies_to_sender(monkeypatch, agent_response):
    replies = {}

    def fake_reply(to_addr, subject, body, pdf_bytes=None, pdf_filename="Trip_Plan.pdf"):
        replies["to"] = to_addr
        replies["subject"] = subject
        replies["body"] = body
        replies["pdf"] = pdf_bytes
        return True

    monkeypatch.setattr(email_mod, "send_email_reply", fake_reply)
    monkeypatch.setattr(email_mod.travel_agent, "handle_message", lambda *a, **k: agent_response)

    msg = _plain_email(from_addr="dana@example.com", subject="Rome please", body="2 adults, next month")
    email_mod._process_email(msg)

    assert replies["to"] == "dana@example.com"
    assert replies["subject"].startswith("Re:")
    assert "Rome, Italy" in replies["body"]
    assert replies["pdf"] is not None


def test_process_email_uses_email_as_session_user(monkeypatch, agent_response):
    captured = {}

    def fake_handle(channel, user_id, message, context=None):
        captured["channel"] = channel
        captured["user_id"] = user_id
        captured["message"] = message
        return agent_response

    monkeypatch.setattr(email_mod, "send_email_reply", lambda *a, **k: True)
    monkeypatch.setattr(email_mod.travel_agent, "handle_message", fake_handle)

    msg = _plain_email(from_addr="bob@example.com", subject="Trip", body="Paris in July")
    email_mod._process_email(msg)

    assert captured["channel"] == "email"
    assert captured["user_id"] == "bob@example.com"
    assert "Paris in July" in captured["message"]


def test_process_email_suppressed_on_human_takeover(monkeypatch):
    reply_called = {"count": 0}
    monkeypatch.setattr(
        email_mod, "send_email_reply",
        lambda *a, **k: reply_called.__setitem__("count", reply_called["count"] + 1),
    )
    suppressed = AgentResponse(text="", meta={"suppressed": True, "reason": "human_takeover"})
    monkeypatch.setattr(email_mod.travel_agent, "handle_message", lambda *a, **k: suppressed)

    msg = _plain_email()
    email_mod._process_email(msg)
    assert reply_called["count"] == 0  # no automated reply during takeover


# --- IMAP polling ------------------------------------------------------------

def test_poll_once_fetches_and_marks_seen(monkeypatch, agent_response):
    processed = []

    fake_imap = MagicMock(name="imap")
    fake_imap.search.return_value = ("OK", [b"1 2"])

    def fake_fetch(num, spec):
        raw = _plain_email(subject=f"msg-{num.decode()}").as_bytes()
        return ("OK", [(b"1", raw)])

    fake_imap.fetch.side_effect = fake_fetch

    monkeypatch.setattr(email_mod.imaplib, "IMAP4_SSL", lambda host, port: fake_imap)
    monkeypatch.setattr(email_mod, "_process_email", lambda m: processed.append(m))
    monkeypatch.setattr(email_mod.config, "IMAP_HOST", "imap.test")
    monkeypatch.setattr(email_mod.config, "IMAP_USER", "u")
    monkeypatch.setattr(email_mod.config, "IMAP_PASSWORD", "p")

    email_mod._poll_once()

    assert len(processed) == 2                      # both unseen messages processed
    # Each message flagged as seen.
    seen_calls = [c for c in fake_imap.store.call_args_list if "\\Seen" in c.args]
    assert len(seen_calls) == 2
    fake_imap.logout.assert_called_once()


def test_email_poller_does_not_start_when_disabled(monkeypatch):
    monkeypatch.setattr(email_mod.config, "EMAIL_ENABLED", False)
    poller = email_mod.EmailPoller()
    poller.start()
    assert poller._thread is None
