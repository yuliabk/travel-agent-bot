"""Log provider failures without logging requests, credentials or raw exceptions."""

import logging
import re

logger = logging.getLogger(__name__)


def log_provider_failure(provider, exc, *, request_id=None, model=None):
    code = getattr(exc, "code", None)
    response = getattr(exc, "response", None)
    if not isinstance(code, int):
        code = getattr(response, "status_code", None)
    if not isinstance(code, int):
        code = None
    # Inspect text only to select fixed labels. Never emit the raw text: HTTP
    # errors can contain API keys in URLs, and validation errors contain input.
    message = str(exc).lower()
    reason = "unknown"
    for needle, label in (
        ("api key expired", "api_key_expired"),
        ("api key not valid", "api_key_invalid"),
        ("api_key_invalid", "api_key_invalid"),
        ("api_key_service_blocked", "api_key_service_blocked"),
        ("quota", "quota_exceeded"),
        ("resource_exhausted", "quota_exceeded"),
        ("permission_denied", "permission_denied"),
        ("not found", "model_or_resource_not_found"),
        ("unknown name", "unsupported_request_field"),
        ("schema", "schema_error"),
        ("structured narrative", "missing_structured_narrative"),
        ("timed out", "timeout"),
    ):
        if needle in message:
            reason = label
            break
    def safe(value):
        value = str(value or "")
        return value if re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", value) else "unknown"
    logger.error(
        "provider_failure provider=%s request_id=%s model=%s exception=%s code=%s reason=%s",
        safe(provider), safe(request_id), safe(model), safe(type(exc).__name__), code, reason,
    )
