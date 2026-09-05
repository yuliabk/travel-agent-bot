"""
YB Travel Agent - multi-channel entry point.

This thin application layer wires together the shared core (agent, session,
logger) and the three channels (WhatsApp, Email, Web Form). All business logic
lives under ``src/`` so every channel behaves identically.

Channels:
* WhatsApp  -> ``GET/POST /webhook``          (Meta Cloud API)
* Web Form  -> ``POST /api/webform``          (structured JSON)
* Email     -> IMAP polling + SMTP (background thread, no HTTP route)
* Contract  -> ``/v1/*``                      (governed Contract v1 API)
"""

import asyncio
import contextlib
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from src.core import config
from src.core.logger import get_logger
from src.core.rate_limit import limiter
from src.core.session import session_manager
from src.channels import whatsapp, webform
from src.channels.email import email_poller
from src.api import v1
from src.api.web_gate_v1 import webform_gate_decision

logger = get_logger("main")

app = FastAPI(title="YB Travel Agent API - Multi-Channel (Gemini Powered)")

# --- Rate limiting (applies a global default limit to every endpoint) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def contract_v1_webform_gate(request: Request, call_next):
    """Protect PII-bearing web intake endpoints with a server-to-server token."""
    enabled = os.getenv("V1_WEBFORM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    expected = os.getenv("V1_WEBFORM_TOKEN", "")
    status, message = webform_gate_decision(
        request.url.path,
        request.headers.get("Authorization"),
        enabled=enabled,
        expected_token=expected,
    )
    if status is not None:
        return JSONResponse(status_code=status, content={"detail": message})
    return await call_next(request)


# --- Channel routers ---
app.include_router(whatsapp.router)
app.include_router(webform.router)
app.include_router(v1.router)


# --- Background: session cleanup (in-memory backend housekeeping) ---
async def _session_cleanup_loop():
    while True:
        await asyncio.sleep(3600)
        removed = session_manager.cleanup()
        if removed:
            logger.info("Session cleanup removed %d expired sessions", removed)


@app.on_event("startup")
async def on_startup():
    logger.info("Starting YB Travel Agent (multi-channel)")
    email_poller.start()  # no-op unless EMAIL_ENABLED and IMAP configured
    app.state.cleanup_task = asyncio.create_task(_session_cleanup_loop())


@app.on_event("shutdown")
async def on_shutdown():
    email_poller.stop()
    task = getattr(app.state, "cleanup_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    logger.info("Shutdown complete")


@app.get("/")
def root():
    return {
        "status": "online",
        "engine": f"Google {config.GEMINI_MODEL}",
        "service": "YB Travel Agent API",
        "channels": {
            "whatsapp": True,
            "webform": True,
            "email": config.EMAIL_ENABLED,
            "contract_v1": True,
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
