"""Vercel-safe Contract v1 FastAPI entrypoint.

This application intentionally excludes legacy WhatsApp, Email polling, session
cleanup background tasks, and PDF generation. It exposes only the governed v1
API surface needed by the migrated webform.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api import v1
from src.api.web_gate_v1 import webform_gate_decision

app = FastAPI(title="YB Travel Agent Contract v1 API")


@app.middleware("http")
async def contract_v1_webform_gate(request: Request, call_next):
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


app.include_router(v1.router)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "YB Travel Agent Contract v1 API",
        "runtime": "vercel",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
