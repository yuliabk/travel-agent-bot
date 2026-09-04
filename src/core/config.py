"""
Central configuration.

All environment variables are read here in one place so the rest of the code
never touches ``os.environ`` directly. This makes missing/misconfigured
variables easy to spot and validate.
"""
import os

try:
    # Optional: load a local .env file when python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional in production
    pass


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- AI (Google Gemini) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# --- SerpApi (flights & hotels) ---
SERPAPI_KEY = os.environ.get("SERPAPI_API_KEY", "")
DEFAULT_ORIGIN_IATA = os.environ.get("DEFAULT_ORIGIN_IATA", "TLV")

# --- Redis (session backend, optional - falls back to in-memory) ---
REDIS_URL = os.environ.get("REDIS_URL", "")

# --- Session ---
# 24h TTL as requested for the shared session store.
SESSION_TTL_SECONDS = _get_int("SESSION_TTL_SECONDS", 24 * 3600)
MAX_HISTORY_MESSAGES = _get_int("MAX_HISTORY_MESSAGES", 20)

# --- WhatsApp Cloud API ---
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "yb_travel_secret_token_2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
# App secret is used to verify the X-Hub-Signature-256 webhook signature.
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
AGENT_PHONE_NUMBER = os.environ.get("AGENT_PHONE_NUMBER", "")

# --- Email channel (IMAP in / SMTP out) ---
EMAIL_ENABLED = _get_bool("EMAIL_ENABLED", False)
IMAP_HOST = os.environ.get("IMAP_HOST", "")
IMAP_PORT = _get_int("IMAP_PORT", 993)
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
IMAP_MAILBOX = os.environ.get("IMAP_MAILBOX", "INBOX")
EMAIL_POLL_INTERVAL_SECONDS = _get_int("EMAIL_POLL_INTERVAL_SECONDS", 60)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = _get_int("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or IMAP_USER
SMTP_USE_TLS = _get_bool("SMTP_USE_TLS", True)

# --- Web form channel ---
# When set, the web form will also email the reply back to the requester.
WEBFORM_SEND_EMAIL_REPLY = _get_bool("WEBFORM_SEND_EMAIL_REPLY", False)

# --- Rate limiting ---
RATE_LIMIT_WEBHOOK = os.environ.get("RATE_LIMIT_WEBHOOK", "120/minute")
RATE_LIMIT_WEBFORM = os.environ.get("RATE_LIMIT_WEBFORM", "10/minute")

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FILE = os.environ.get("LOG_FILE", "travel_agent.log")
