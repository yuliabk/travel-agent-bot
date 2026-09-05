"""Fail-closed server-to-server gate for Contract v1 web intake endpoints."""

from __future__ import annotations

import hmac
from typing import Optional, Tuple

PROTECTED_WEB_PATHS = frozenset({
    "/v1/web/draft",
    "/v1/web/map-points",
    "/v1/web/destinations",
    "/v1/intake/abacus/normalize",
})


def webform_gate_decision(
    path: str,
    authorization: Optional[str],
    *,
    enabled: bool,
    expected_token: str,
) -> Tuple[Optional[int], Optional[str]]:
    """Return an HTTP status/message when access must be blocked, else (None, None)."""
    if path not in PROTECTED_WEB_PATHS:
        return None, None
    if not enabled or not expected_token:
        return 503, "Contract v1 web intake is disabled"
    if not authorization or not authorization.startswith("Bearer "):
        return 401, "missing webform bearer token"
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected_token):
        return 403, "invalid webform bearer token"
    return None, None
