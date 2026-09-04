"""
Email channel - IMAP polling in, SMTP reply out.

A background thread polls the mailbox every ``EMAIL_POLL_INTERVAL_SECONDS``
(default 60s) for unseen messages, feeds each one through the shared agent core
and replies via SMTP (attaching the generated PDF when available).

Uses only the Python standard library (``imaplib``, ``smtplib``, ``email``) so
no extra native dependencies are required.
"""

import email
import imaplib
import smtplib
import threading
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr

from src.core import config
from src.core.agent import travel_agent
from src.core.logger import get_logger

logger = get_logger("channel.email")

CHANNEL = "email"


def _decode(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _extract_body(msg: email.message.Message) -> str:
    """Return the best-effort plain-text body of an email message."""
    if msg.is_multipart():
        # Prefer text/plain, skip attachments.
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace").strip()
                except Exception:
                    continue
        # Fallback to any text/html stripped of tags (very light).
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    import re

                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    return re.sub(r"<[^>]+>", " ", html).strip()
                except Exception:
                    continue
        return ""
    try:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace").strip()
    except Exception:
        return ""


def send_email_reply(to_addr: str, subject: str, body: str, pdf_bytes=None, pdf_filename="Trip_Plan.pdf") -> bool:
    if not config.SMTP_HOST or not config.SMTP_USER:
        logger.info("[LOCAL LOG email to %s] %s\n%s", to_addr, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM or config.SMTP_USER
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    if pdf_bytes is not None:
        try:
            msg.add_attachment(
                pdf_bytes.getvalue(),
                maintype="application",
                subtype="pdf",
                filename=pdf_filename,
            )
        except Exception as exc:
            logger.warning("Failed to attach PDF to email: %s", exc)
    try:
        if config.SMTP_USE_TLS:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
        logger.info("Sent email reply to %s", to_addr)
        return True
    except Exception as exc:
        logger.error("send_email_reply failed for %s: %s", to_addr, exc)
        return False


def _process_email(msg: email.message.Message) -> None:
    from_addr = parseaddr(msg.get("From"))[1]
    subject = _decode(msg.get("Subject")) or "בקשת תכנון טיול"
    body = _extract_body(msg)
    if not from_addr:
        logger.warning("Email with no sender address - skipping")
        return

    combined = f"{subject}\n\n{body}".strip()
    logger.info("Processing email from %s (subject=%s)", from_addr, subject)

    result = travel_agent.handle_message(CHANNEL, from_addr, combined, context={"subject": subject})
    if not result.text and result.meta.get("suppressed"):
        return  # human takeover - stay silent

    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    send_email_reply(
        to_addr=from_addr,
        subject=reply_subject,
        body=result.text or "קיבלנו את פנייתכם ונחזור אליכם בהקדם.",
        pdf_bytes=result.pdf_bytes,
        pdf_filename=result.pdf_filename or "Trip_Plan.pdf",
    )


def _poll_once() -> None:
    imap = None
    try:
        imap = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        imap.login(config.IMAP_USER, config.IMAP_PASSWORD)
        imap.select(config.IMAP_MAILBOX)
        status_, data = imap.search(None, "UNSEEN")
        if status_ != "OK":
            return
        ids = data[0].split()
        for num in ids:
            fetch_status, msg_data = imap.fetch(num, "(RFC822)")
            if fetch_status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw)
            try:
                _process_email(message)
            except Exception as exc:
                logger.exception("Failed to process one email: %s", exc)
            finally:
                # Mark as seen so we never reprocess the same request.
                imap.store(num, "+FLAGS", "\\Seen")
    except Exception as exc:
        logger.error("IMAP poll failed: %s", exc)
    finally:
        if imap is not None:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass


class EmailPoller:
    """Background thread that polls IMAP on an interval."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = None

    def _run(self) -> None:
        interval = max(15, config.EMAIL_POLL_INTERVAL_SECONDS)
        logger.info("Email poller started (every %ss, mailbox=%s)", interval, config.IMAP_MAILBOX)
        while not self._stop.is_set():
            _poll_once()
            self._stop.wait(interval)
        logger.info("Email poller stopped")

    def start(self) -> None:
        if not config.EMAIL_ENABLED:
            logger.info("Email channel disabled (EMAIL_ENABLED is false)")
            return
        if not (config.IMAP_HOST and config.IMAP_USER and config.IMAP_PASSWORD):
            logger.warning("Email channel enabled but IMAP settings incomplete - not starting")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="email-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


email_poller = EmailPoller()
