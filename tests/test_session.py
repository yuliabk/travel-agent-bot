"""Tests for the session manager (src/core/session.py)."""
import time

import pytest

from src.core import session as session_mod
from src.core.session import SessionManager, _MemoryBackend, _empty_session, _make_key


# --- New session creation ----------------------------------------------------

def test_get_returns_fresh_empty_session():
    mgr = SessionManager()
    s = mgr.get("whatsapp", "user-1")
    assert s == _empty_session()
    assert s["current_itinerary"] is None
    assert s["is_human_takeover"] is False
    assert s["history"] == []


def test_empty_session_is_independent_copy():
    a = _empty_session()
    b = _empty_session()
    a["history"].append({"role": "user", "text": "hi"})
    assert b["history"] == []


def test_sessions_are_isolated_per_channel_and_user():
    mgr = SessionManager()
    s = mgr.get("whatsapp", "user-1")
    s["is_human_takeover"] = True
    mgr.save("whatsapp", "user-1", s)

    # Different channel, same user id -> independent session
    other = mgr.get("email", "user-1")
    assert other["is_human_takeover"] is False
    # Different user, same channel -> independent session
    other2 = mgr.get("whatsapp", "user-2")
    assert other2["is_human_takeover"] is False


def test_make_key_format():
    assert _make_key("email", "a@b.com") == "travel_session:email:a@b.com"


# --- Save & retrieve ---------------------------------------------------------

def test_save_and_reload_roundtrip():
    mgr = SessionManager()
    s = mgr.get("webform", "dana")
    s["current_itinerary"] = {"destination": "Rome"}
    s["flights_data"] = [{"airline": "ELAL"}]
    mgr.save("webform", "dana", s)

    reloaded = mgr.get("webform", "dana")
    assert reloaded["current_itinerary"] == {"destination": "Rome"}
    assert reloaded["flights_data"] == [{"airline": "ELAL"}]


# --- History management ------------------------------------------------------

def test_append_history_adds_entries():
    mgr = SessionManager()
    s = mgr.get("whatsapp", "u")
    mgr.append_history(s, "user", "hello")
    mgr.append_history(s, "assistant", "hi there")
    assert len(s["history"]) == 2
    assert s["history"][0]["role"] == "user"
    assert s["history"][0]["text"] == "hello"
    assert "ts" in s["history"][0]


def test_history_is_bounded_on_save(monkeypatch):
    # conftest sets MAX_HISTORY_MESSAGES=6
    from src.core import config

    mgr = SessionManager()
    s = mgr.get("whatsapp", "u")
    for i in range(20):
        mgr.append_history(s, "user", f"msg-{i}")
    mgr.save("whatsapp", "u", s)

    reloaded = mgr.get("whatsapp", "u")
    assert len(reloaded["history"]) == config.MAX_HISTORY_MESSAGES
    # Only the most recent messages are retained.
    assert reloaded["history"][-1]["text"] == "msg-19"


# --- Delete ------------------------------------------------------------------

def test_delete_removes_session():
    mgr = SessionManager()
    s = mgr.get("whatsapp", "gone")
    s["current_itinerary"] = {"x": 1}
    mgr.save("whatsapp", "gone", s)
    mgr.delete("whatsapp", "gone")
    assert mgr.get("whatsapp", "gone") == _empty_session()


# --- TTL / expiry (memory backend) ------------------------------------------

def test_memory_backend_expires_after_ttl(monkeypatch):
    backend = _MemoryBackend()
    t = {"now": 1000.0}
    monkeypatch.setattr(session_mod.time, "time", lambda: t["now"])

    backend.set("k", {"v": 1}, ttl=100)
    assert backend.get("k") == {"v": 1}

    # Advance beyond TTL -> entry must be gone.
    t["now"] = 1101.0
    assert backend.get("k") is None


def test_memory_backend_cleanup_purges_expired(monkeypatch):
    backend = _MemoryBackend()
    t = {"now": 500.0}
    monkeypatch.setattr(session_mod.time, "time", lambda: t["now"])

    backend.set("a", {"v": 1}, ttl=10)
    backend.set("b", {"v": 2}, ttl=10000)
    t["now"] = 600.0  # 'a' expired, 'b' still valid
    removed = backend.cleanup()
    assert removed == 1
    assert backend.get("a") is None
    assert backend.get("b") == {"v": 2}


def test_memory_backend_not_expired_within_ttl(monkeypatch):
    backend = _MemoryBackend()
    t = {"now": 0.0}
    monkeypatch.setattr(session_mod.time, "time", lambda: t["now"])
    backend.set("k", {"v": 1}, ttl=100)
    t["now"] = 50.0
    assert backend.get("k") == {"v": 1}
