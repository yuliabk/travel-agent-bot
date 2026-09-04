"""
WhatsApp channel (Meta Cloud API).

Responsibilities:
* Verify the webhook subscription (GET) and the request signature (POST).
* Convert inbound WhatsApp messages (text/audio) into agent-core calls.
* Send text + PDF replies back through the Cloud API.

All heavy work runs in a FastAPI background task so the webhook returns 200
immediately (Meta retries otherwise).
"""
import hashlib
import hmac
import io

import requests
from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from src.core import config
from src.core.agent import travel_agent
from src.core.logger import get_logger
from src.core.session import session_manager

logger = get_logger("channel.whatsapp")
router = APIRouter(tags=["whatsapp"])

CHANNEL = "whatsapp"
GRAPH_BASE = "https://graph.facebook.com/v20.0"


# --- Outbound helpers ---------------------------------------------------

def send_whatsapp_text(to_phone: str, text: str) -> None:
    if not text:
        return
    if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_ID:
        logger.info("[LOCAL LOG to %s]: %s", to_phone, text)
        return
    url = f"{GRAPH_BASE}/{config.WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": True, "body": text},
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("send_whatsapp_text failed for %s: %s", to_phone, exc)


def mark_message_as_read(message_id: str) -> None:
    if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_ID or not message_id:
        return
    url = f"{GRAPH_BASE}/{config.WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception as exc:
        logger.warning("mark_message_as_read failed: %s", exc)


def download_and_transcribe_audio(media_id: str) -> str:
    """Download a WhatsApp voice note and transcribe it to Hebrew via Gemini."""
    if not media_id or not travel_agent.ai_client:
        return ""
    try:
        from google.genai import types

        headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}
        meta = requests.get(f"{GRAPH_BASE}/{media_id}", headers=headers, timeout=10).json()
        download_url = meta.get("url")
        if not download_url:
            logger.warning("No download URL for media %s", media_id)
            return ""
        audio_bytes = requests.get(download_url, headers=headers, timeout=15).content
        response = travel_agent.ai_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                "תמלל במדויק מילה במילה את ההקלטה הקולית הזו לעברית. "
                "החזר אך ורק את הטקסט המתומלל ללא שום הקדמות או תוספות.",
            ],
        )
        return (response.text or "").strip()
    except Exception as exc:
        logger.error("Audio transcription failed for %s: %s", media_id, exc)
        return ""


def upload_and_send_pdf(to_phone: str, pdf_bytes: io.BytesIO, filename: str, caption: str) -> None:
    if pdf_bytes is None:
        return
    if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_ID:
        logger.info("[LOCAL LOG] PDF generated (%d bytes) for %s", len(pdf_bytes.getvalue()), to_phone)
        return
    try:
        upload_url = f"{GRAPH_BASE}/{config.WHATSAPP_PHONE_ID}/media"
        headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}
        files = {"file": (filename, pdf_bytes.getvalue(), "application/pdf")}
        data = {"messaging_product": "whatsapp", "type": "application/pdf"}
        up_res = requests.post(upload_url, headers=headers, files=files, data=data, timeout=25)
        up_res.raise_for_status()
        media_id = up_res.json().get("id")

        msg_url = f"{GRAPH_BASE}/{config.WHATSAPP_PHONE_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "document",
            "document": {"id": media_id, "filename": filename, "caption": caption},
        }
        requests.post(
            msg_url,
            headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
    except Exception as exc:
        logger.error("upload_and_send_pdf failed for %s: %s", to_phone, exc)


# --- Security -----------------------------------------------------------

def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """Validate Meta's ``X-Hub-Signature-256`` header.

    If ``WHATSAPP_APP_SECRET`` is not configured we log a warning and allow the
    request (keeps local/dev usable) but this should always be set in prod.
    """
    if not config.WHATSAPP_APP_SECRET:
        logger.warning("WHATSAPP_APP_SECRET not set - skipping signature verification")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        config.WHATSAPP_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


# --- Background processing ---------------------------------------------

def process_interaction(sender_phone: str, msg_type: str, msg_data: dict) -> None:
    try:
        msg_id = msg_data.get("id")
        if msg_id:
            mark_message_as_read(msg_id)

        raw_text = (
            msg_data.get("text", {}).get("body", "").strip() if msg_type == "text" else ""
        )

        # Agent /resume command to release a human-takeover session.
        if sender_phone == config.AGENT_PHONE_NUMBER and raw_text.startswith("/resume"):
            parts = raw_text.split()
            if len(parts) > 1:
                target = parts[1]
                t_session = session_manager.get(CHANNEL, target)
                t_session["is_human_takeover"] = False
                session_manager.save(CHANNEL, target, t_session)
                send_whatsapp_text(config.AGENT_PHONE_NUMBER, f"✅ הבוט הופשר בהצלחה עבור {target}")
                send_whatsapp_text(target, "השיחה חזרה למענה האוטומטי. נשמח להמשיך לסייע בתכנון החופשה! 🌍")
            return

        # Immediate acknowledgement + resolve message text.
        if msg_type == "audio":
            send_whatsapp_text(
                sender_phone,
                "היי! קיבלנו את ההקלטה שלך 🎧 מתמללים את הבקשה, בודקים טיסות ומלונות ומכינים הצעה מסודרת...",
            )
            user_text = download_and_transcribe_audio(msg_data.get("audio", {}).get("id"))
        else:
            send_whatsapp_text(
                sender_phone,
                "היי! קיבלנו את הבקשה ✈️ כבר בודקים טיסות, מלונות ומפיקים עבורך מסמך טיול אישי ומפורט...",
            )
            user_text = raw_text

        if not user_text:
            send_whatsapp_text(sender_phone, "לא הצלחנו לקרוא את ההודעה. נשמח שתכתבו לנו יעד ותאריכים.")
            return

        result = travel_agent.handle_message(CHANNEL, sender_phone, user_text)

        # Notify agent on handoff.
        if result.handoff and config.AGENT_PHONE_NUMBER:
            send_whatsapp_text(
                config.AGENT_PHONE_NUMBER,
                f"🚨 *התראת העברה לנציג אנושי!*\nלקוח: wa.me/{sender_phone}\n"
                f"סיבה: {result.handoff_reason}\nהודעה: \"{user_text}\"\nלשחרור: /resume {sender_phone}",
            )

        if result.text:
            send_whatsapp_text(sender_phone, result.text)
        if result.pdf_bytes is not None:
            upload_and_send_pdf(
                sender_phone,
                result.pdf_bytes,
                result.pdf_filename or "Trip_Plan.pdf",
                f"הצעת מחיר ותוכנית טיול - {result.destination or ''}",
            )
    except Exception as exc:
        logger.exception("process_interaction failed for %s: %s", sender_phone, exc)
        send_whatsapp_text(
            sender_phone,
            "היי, התחלנו לעבד את הבקשה אך חסרים לנו מעט פרטים (יעד או תאריכים). נשמח לפירוט קצר.",
        )


# --- Routes -------------------------------------------------------------

@router.get("/webhook")
def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()

    if not verify_signature(raw_body, request.headers.get("X-Hub-Signature-256", "")):
        logger.warning("Rejected WhatsApp webhook with invalid signature")
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            msg_type = msg.get("type")
            sender_phone = msg.get("from")
            if msg_type in ("text", "audio") and sender_phone:
                background_tasks.add_task(
                    process_interaction,
                    sender_phone=sender_phone,
                    msg_type=msg_type,
                    msg_data=msg,
                )
    except (IndexError, KeyError, TypeError):
        # Non-message events (status updates, etc.) - safe to ignore.
        pass
    return Response(status_code=status.HTTP_200_OK)
