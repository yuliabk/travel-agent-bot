# YB Travel Agent — Multi-Channel AI Bot 🌍✈️

## Keyless open travel providers

Contract v1 can use two optional, read-only sources without credentials when
`V1_OPEN_TRAVEL_ENABLED=true`:

- OctoTrip Rental Cars MCP for observed rental-car comparison quotes.
- Wikidata for attraction identity, descriptions and official-site links.

Neither source is treated as booking-ready evidence. Rental prices must be
rechecked with the linked supplier, and missing attraction admission prices
remain unknown rather than being interpreted as free.

> **עברית + English** · AI travel agent powered by **Google Gemini**, now serving **three channels** through a single shared brain: **WhatsApp**, **Email**, and a structured **Web Form**.

---

## 🇮🇱 עברית

סוכן נסיעות חכם מבוסס AI. לקוח יכול לפנות **בשלוש דרכים** — וכולן עוברות דרך אותו מנוע AI משותף (`agent core`), עם אותו זיכרון שיחה, אותה לוגיקה ואותו פלט (הודעת סיכום + קובץ PDF מעוצב):

1. **WhatsApp** — דרך Meta Cloud API (טקסט + הודעות קוליות).
2. **Email** — המערכת סורקת תיבת דואר כל 60 שניות (IMAP), מעבדת את הפנייה ומשיבה במייל (SMTP) עם ה-PDF מצורף.
3. **טופס באתר** — נקודת קצה `POST /api/webform` שמקבלת JSON מובנה (שם, אימייל, טלפון, פרטי טיול).

### ארכיטקטורה
```
src/
├── core/
│   ├── config.py        # כל משתני הסביבה במקום אחד
│   ├── logger.py        # לוגים לקובץ + קונסול (rotating)
│   ├── session.py       # ניהול sessions עם TTL (Redis או in-memory) + זיכרון שיחה
│   ├── agent.py         # ה-"מוח" המשותף: טריאז', חילוץ דרישות, בניית/עדכון מסלול
│   ├── travel_tools.py  # חיפוש טיסות/מלונות (SerpApi) + הפקת PDF (WeasyPrint)
│   └── rate_limit.py    # מגביל קצב משותף (slowapi)
└── channels/
    ├── whatsapp.py      # handler לוואטסאפ + אימות חתימת webhook
    ├── email.py         # IMAP polling + מענה SMTP
    └── webform.py       # endpoint לטופס מובנה
main.py                  # חיווט: FastAPI, routers, rate limiting, מתזמן רקע
```

### רכיבי המערכת
- **FastAPI** — שרת ה-API וה-Webhook.
- **Google Gemini 2.5 Flash** — תמלול קול, טריאז', חילוץ דרישות ותכנון מסלול (Structured Outputs).
- **SerpApi** — טיסות (Google Flights) ומלונות (Google Hotels, השוואת Booking/Agoda).
- **WeasyPrint** — הפקת PDF מעוצב בעברית עם קישורי Google Maps.
- **Redis / In-Memory** — ניהול sessions וזיכרון שיחה (עם fallback אוטומטי).
- **slowapi** — הגבלת קצב לכל נקודות הקצה.
- **Human-in-the-loop** — הקפאת בוט והעברה לנציג אנושי (פקודת `/resume`).

### הרצה מקומית
```bash
pip install -r requirements.txt
cp .env.example .env      # מלאו את המפתחות
uvicorn main:app --reload --port 8000
```

---

## 🇬🇧 English

An AI travel agent where a client can reach out through **three channels**, all routed to the same shared **agent core** (same memory, logic and output — a summary message + a styled PDF):

1. **WhatsApp** — via Meta Cloud API (text + voice notes).
2. **Email** — polls a mailbox every 60s (IMAP), processes the request and replies via SMTP with the PDF attached.
3. **Web Form** — a `POST /api/webform` endpoint that accepts a structured JSON body.

### Configuration
All settings come from environment variables — see **`.env.example`** for the full, documented list. Copy it to `.env` and fill in what you need. Only `GEMINI_API_KEY` is strictly required; each channel activates when its own variables are set.

### Channel details

**1) WhatsApp** — `GET/POST /webhook`
- `GET /webhook` handles Meta's subscription verification (`WHATSAPP_VERIFY_TOKEN`).
- `POST /webhook` verifies the `X-Hub-Signature-256` HMAC signature using `WHATSAPP_APP_SECRET`, then processes text/audio in a background task.
- Requires: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `AGENT_PHONE_NUMBER`.

**2) Email** — background IMAP poller + SMTP replies
- Set `EMAIL_ENABLED=true` and configure the `IMAP_*` and `SMTP_*` variables.
- Polls `IMAP_MAILBOX` every `EMAIL_POLL_INTERVAL_SECONDS` (default 60) for **unseen** messages, replies in-thread and marks them seen.

**3) Web Form** — `POST /api/webform`
```jsonc
{
  "name": "Dana Levi",
  "email": "dana@example.com",
  "phone": "+972500000000",
  "tripDetails": {
    "destination": "Rome, Italy",
    "dates": "10-17 August 2026",
    "budget": "1500 USD per person",
    "travelers": "2 adults + 1 child",
    "preferences": "kosher food, relaxed pace, art museums"
  }
}
```
Response:
```jsonc
{
  "success": true,
  "message": "…summary text…",
  "destination": "Rome, Italy",
  "handoff": false,
  "pdf_base64": "…base64 PDF…",   // null if PDF could not be generated
  "email_sent": false              // true if WEBFORM_SEND_EMAIL_REPLY and email provided
}
```
Set `WEBFORM_SEND_EMAIL_REPLY=true` (with SMTP configured) to also email the reply + PDF to the requester.

### Rate limiting
`slowapi` applies a global default limit (`RATE_LIMIT_WEBHOOK`) to every endpoint, with a stricter per-route limit on the web form (`RATE_LIMIT_WEBFORM`).

### Run
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Docker
```bash
docker build -t yb-travel-agent .
docker run -p 8000:8000 --env-file .env yb-travel-agent
```

---

### Notes / What changed in the multi-channel upgrade
- Refactored the original monolithic `main.py` into a shared **core** + pluggable **channels**.
- Added **Email** and **Web Form** channels alongside the existing WhatsApp flow.
- Added **webhook signature verification**, hardened **error handling** across all network/AI calls, **rate limiting**, structured **logging**, **session TTL + cleanup** with an in-memory fallback, and conversation **memory** per user per channel.
