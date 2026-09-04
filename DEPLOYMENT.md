# Deployment Guide · מדריך פריסה

> YB Travel Agent — multi-channel AI travel bot (FastAPI + Redis + Docker).
> This guide covers **Docker Compose (VPS)**, **Railway.app**, and **Render.com**, plus the full list of required environment variables.

---

## 🇮🇱 עברית

### תוכן עניינים
1. [משתני סביבה נדרשים](#env-he)
2. [אפשרות א׳ — Docker Compose (VPS)](#compose-he)
3. [אפשרות ב׳ — Railway.app (הכי פשוט)](#railway-he)
4. [אפשרות ג׳ — Render.com](#render-he)
5. [CI/CD אוטומטי (GitHub Actions)](#cicd-he)

<a name="env-he"></a>
### 1. משתני סביבה נדרשים
העתיקו את `.env.example` ל-`.env` ומלאו את הערכים. **חובה** רק `GEMINI_API_KEY` — כל ערוץ מופעל כשמגדירים את המשתנים שלו.

| משתנה | חובה? | תיאור |
|-------|-------|-------|
| `GEMINI_API_KEY` | ✅ חובה | מפתח Google Gemini (מנוע ה-AI) |
| `GEMINI_MODEL` | אופ׳ | ברירת מחדל: `gemini-2.5-flash` |
| `SERPAPI_API_KEY` | אופ׳ | חיפוש טיסות/מלונות (אם ריק — מדלגים) |
| `DEFAULT_ORIGIN_IATA` | אופ׳ | קוד שדה מוצא, ברירת מחדל `TLV` |
| `REDIS_URL` | מומלץ | כתובת Redis; אם ריק — נעשה שימוש בזיכרון מקומי |
| `SESSION_TTL_SECONDS` | אופ׳ | תוקף שיחה, ברירת מחדל 86400 (24 שעות) |
| `MAX_HISTORY_MESSAGES` | אופ׳ | מספר הודעות שנשמרות בזיכרון השיחה |
| **WhatsApp** | | |
| `WHATSAPP_ACCESS_TOKEN` | לערוץ WA | טוקן Meta Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | לערוץ WA | מזהה מספר הטלפון |
| `WHATSAPP_VERIFY_TOKEN` | לערוץ WA | טוקן אימות ה-webhook |
| `WHATSAPP_APP_SECRET` | מומלץ מאוד | לאימות חתימת `X-Hub-Signature-256` |
| `AGENT_PHONE_NUMBER` | לערוץ WA | טלפון הנציג האנושי (העברת שיחה) |
| **Email** | | |
| `EMAIL_ENABLED` | לערוץ מייל | `true` להפעלת סריקת IMAP |
| `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASSWORD` / `IMAP_MAILBOX` | לערוץ מייל | הגדרות תיבה נכנסת |
| `EMAIL_POLL_INTERVAL_SECONDS` | אופ׳ | תדירות סריקה, ברירת מחדל 60 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_USE_TLS` | לערוץ מייל | הגדרות שליחה |
| **Web Form** | | |
| `WEBFORM_SEND_EMAIL_REPLY` | אופ׳ | `true` לשליחת תשובה גם במייל |
| **Rate limiting / Logging** | | |
| `RATE_LIMIT_WEBHOOK` / `RATE_LIMIT_WEBFORM` | אופ׳ | מגבלות קצב |
| `LOG_LEVEL` / `LOG_DIR` / `LOG_FILE` | אופ׳ | הגדרות לוגים |

<a name="compose-he"></a>
### 2. אפשרות א׳ — Docker Compose (VPS)
מתאים לשרת פרטי (DigitalOcean / AWS EC2 / Hetzner וכו׳) עם Docker מותקן.

```bash
# 1. שכפול המאגר
git clone https://github.com/yuliabk/travel-agent-bot.git
cd travel-agent-bot

# 2. הגדרת משתני סביבה
cp .env.example .env
nano .env          # מלאו את המפתחות

# 3. הרמת הסטאק (bot + redis)
docker compose up -d --build

# 4. בדיקת בריאות
curl http://localhost:8000/health      # מצופה: {"status":"ok"}
docker compose logs -f bot
```
`docker-compose.yml` כולל Redis עם persistence (AOF), health checks לשני השירותים, ו-volume ללוגים (`./logs`). ה-bot ממתין ש-Redis יהיה בריא לפני שהוא עולה.

**עדכון גרסה:**
```bash
git pull && docker compose up -d --build
```

**Webhook של WhatsApp:** יש לחשוף את הפורט לאינטרנט עם HTTPS (למשל דרך Nginx + Let's Encrypt או Cloudflare Tunnel) ולהגדיר את ה-URL `https://your-domain/webhook` בלוח הבקרה של Meta.

<a name="railway-he"></a>
### 3. אפשרות ב׳ — Railway.app (הכי פשוט)
1. היכנסו ל-[railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → בחרו `travel-agent-bot`.
2. Railway מזהה את ה-`Dockerfile` אוטומטית ובונה את ה-image.
3. הוסיפו שירות **Redis**: **New** → **Database** → **Add Redis**. Railway יזריק אוטומטית משתנה חיבור — הגדירו `REDIS_URL` שיצביע עליו (למשל `${{Redis.REDIS_URL}}`).
4. תחת **Variables** הוסיפו את כל המשתנים מהטבלה למעלה (`GEMINI_API_KEY` וכו׳).
5. Railway מקצה דומיין ציבורי אוטומטית. כתובת ה-webhook תהיה `https://<app>.up.railway.app/webhook`.

<a name="render-he"></a>
### 4. אפשרות ג׳ — Render.com
1. [render.com](https://render.com) → **New** → **Web Service** → חברו את מאגר ה-GitHub.
2. **Runtime: Docker** (Render משתמש ב-`Dockerfile`). Health Check Path: `/health`.
3. הוסיפו **Redis** דרך **New → Redis** והעתיקו את ה-Internal URL אל `REDIS_URL`.
4. תחת **Environment** הוסיפו את שאר המשתנים.
5. ה-webhook: `https://<service>.onrender.com/webhook`.

<a name="cicd-he"></a>
### 5. CI/CD אוטומטי
- **`.github/workflows/ci.yml`** — רץ על כל push ל-main וכל PR: בדיקות (pytest), lint (flake8 + black), ובניית Docker image.
- **`.github/workflows/deploy.yml`** — רץ על push ל-main, ורק **לאחר שהבדיקות עברו** בונה ודוחף image ל-`ghcr.io/yuliabk/travel-agent-bot`.

משיכת ה-image מ-GHCR:
```bash
docker pull ghcr.io/yuliabk/travel-agent-bot:latest
```

---

## 🇬🇧 English

### Table of contents
1. [Required environment variables](#env-en)
2. [Option A — Docker Compose (VPS)](#compose-en)
3. [Option B — Railway.app (easiest)](#railway-en)
4. [Option C — Render.com](#render-en)
5. [Automated CI/CD](#cicd-en)

<a name="env-en"></a>
### 1. Required environment variables
Copy `.env.example` to `.env` and fill in the values. Only `GEMINI_API_KEY` is strictly required; each channel activates once its own variables are set. See the Hebrew table above (or `.env.example`) for the full annotated list — the key ones:

- **AI (required):** `GEMINI_API_KEY`, optional `GEMINI_MODEL`.
- **Flights/Hotels (optional):** `SERPAPI_API_KEY`, `DEFAULT_ORIGIN_IATA`.
- **Sessions (recommended):** `REDIS_URL` (falls back to in-memory), `SESSION_TTL_SECONDS`, `MAX_HISTORY_MESSAGES`.
- **WhatsApp:** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` (strongly recommended), `AGENT_PHONE_NUMBER`.
- **Email:** `EMAIL_ENABLED`, `IMAP_*`, `SMTP_*`, `EMAIL_POLL_INTERVAL_SECONDS`.
- **Web Form:** `WEBFORM_SEND_EMAIL_REPLY`.
- **Rate limiting / Logging:** `RATE_LIMIT_WEBHOOK`, `RATE_LIMIT_WEBFORM`, `LOG_LEVEL`, `LOG_DIR`, `LOG_FILE`.

<a name="compose-en"></a>
### 2. Option A — Docker Compose (VPS)
For any VPS (DigitalOcean / AWS EC2 / Hetzner …) with Docker installed:

```bash
git clone https://github.com/yuliabk/travel-agent-bot.git
cd travel-agent-bot
cp .env.example .env      # fill in your keys
docker compose up -d --build
curl http://localhost:8000/health   # -> {"status":"ok"}
docker compose logs -f bot
```
The included `docker-compose.yml` runs the `bot` and a persistent `redis` (AOF) with health checks on both, a `./logs` volume, and the bot waiting for Redis to be healthy before starting.

Update: `git pull && docker compose up -d --build`.

**WhatsApp webhook:** expose the port over HTTPS (Nginx + Let's Encrypt, or a Cloudflare Tunnel) and register `https://your-domain/webhook` in the Meta dashboard.

<a name="railway-en"></a>
### 3. Option B — Railway.app (easiest)
1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → pick `travel-agent-bot`.
2. Railway auto-detects the `Dockerfile` and builds the image.
3. Add a **Redis** plugin (**New → Database → Add Redis**) and set `REDIS_URL` to reference it (e.g. `${{Redis.REDIS_URL}}`).
4. Under **Variables**, add every variable from the table above.
5. Railway assigns a public domain; the webhook URL is `https://<app>.up.railway.app/webhook`.

<a name="render-en"></a>
### 4. Option C — Render.com
1. [render.com](https://render.com) → **New → Web Service** → connect the repo.
2. **Runtime: Docker** (uses the `Dockerfile`); set the Health Check Path to `/health`.
3. Add **Redis** (**New → Redis**) and copy its Internal URL into `REDIS_URL`.
4. Add the remaining variables under **Environment**.
5. Webhook URL: `https://<service>.onrender.com/webhook`.

<a name="cicd-en"></a>
### 5. Automated CI/CD
- **`.github/workflows/ci.yml`** — on every push to main and every PR: `test` (pytest), `lint` (flake8 + black --check), and `build` (Docker image build).
- **`.github/workflows/deploy.yml`** — on push to main, and only **after tests pass**, builds and pushes the image to `ghcr.io/yuliabk/travel-agent-bot`.

Pull the published image:
```bash
docker pull ghcr.io/yuliabk/travel-agent-bot:latest
```

> **Note:** The GHCR package is private by default. To pull without auth, make the package public in the repo's *Packages* settings, or `docker login ghcr.io` with a PAT that has `read:packages`.
