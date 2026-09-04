"""
Web Form channel - a structured HTTP endpoint (``POST /api/webform``).

Accepts a validated JSON body describing a trip request, converts it into a
natural-language brief, runs it through the shared agent core, and returns a
JSON response. When configured, it can also email the reply (with the PDF) back
to the requester.
"""
import base64
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field

from src.core import config
from src.core.agent import travel_agent
from src.core.logger import get_logger
from src.core.rate_limit import limiter

logger = get_logger("channel.webform")
router = APIRouter(prefix="/api", tags=["webform"])

CHANNEL = "webform"


class TripDetails(BaseModel):
    destination: str = Field(..., min_length=2)
    dates: Optional[str] = Field(None, description="Free-text dates, e.g. '10-17 August 2026'")
    budget: Optional[str] = None
    travelers: Optional[str] = Field(None, description="e.g. '2 adults + 1 child'")
    preferences: Optional[str] = None


class WebFormRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tripDetails: TripDetails


class WebFormResponse(BaseModel):
    success: bool
    message: str
    destination: Optional[str] = None
    handoff: bool = False
    pdf_base64: Optional[str] = None
    email_sent: bool = False


def _build_brief(req: WebFormRequest) -> str:
    """Turn the structured form into a natural-language brief for the agent."""
    d = req.tripDetails
    lines = [f"פנייה מלקוח בשם {req.name} דרך טופס האתר.", f"יעד מבוקש: {d.destination}."]
    if d.dates:
        lines.append(f"תאריכים: {d.dates}.")
    if d.travelers:
        lines.append(f"הרכב נוסעים: {d.travelers}.")
    if d.budget:
        lines.append(f"תקציב: {d.budget}.")
    if d.preferences:
        lines.append(f"העדפות ודגשים: {d.preferences}.")
    return "\n".join(lines)


@router.post("/webform", response_model=WebFormResponse)
@limiter.limit(config.RATE_LIMIT_WEBFORM)
def submit_webform(request: Request, req: WebFormRequest):
    # A stable per-user id: prefer email, then phone, then name.
    user_id = req.email or req.phone or req.name
    brief = _build_brief(req)
    logger.info("Web form submission from %s (dest=%s)", user_id, req.tripDetails.destination)

    result = travel_agent.handle_message(
        CHANNEL, user_id, brief, context={"name": req.name, "email": req.email}
    )

    pdf_b64 = None
    if result.pdf_bytes is not None:
        try:
            pdf_b64 = base64.b64encode(result.pdf_bytes.getvalue()).decode("ascii")
        except Exception as exc:
            logger.warning("Failed to base64-encode PDF: %s", exc)

    email_sent = False
    if config.WEBFORM_SEND_EMAIL_REPLY and req.email and result.text:
        try:
            # Rewind the buffer before reusing it for the email attachment.
            if result.pdf_bytes is not None:
                result.pdf_bytes.seek(0)
            from src.channels.email import send_email_reply

            email_sent = send_email_reply(
                to_addr=req.email,
                subject=f"תוכנית הטיול שלך ל{result.destination or req.tripDetails.destination}",
                body=result.text,
                pdf_bytes=result.pdf_bytes,
                pdf_filename=result.pdf_filename or "Trip_Plan.pdf",
            )
        except Exception as exc:
            logger.error("Web form email reply failed: %s", exc)

    return WebFormResponse(
        success=not result.error,
        message=result.text,
        destination=result.destination,
        handoff=result.handoff,
        pdf_base64=pdf_b64,
        email_sent=email_sent,
    )
