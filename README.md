# YB Travel Agent - WhatsApp AI Bot

סוכן נסיעות חכם מבוסס AI הפועל בוואטסאפ.

## רכיבי המערכת
- **FastAPI**: שרת Webhook לקליטת הודעות וואטסאפ בזמן אמת.
- **OpenAI (GPT-4o & Whisper)**: תמלול הודעות קוליות ותכנון מסלול מותאם אישית.
- **SerpApi**: איתור טיסות בזמן אמת מ-Google Flights ומלונות מ-Google Hotels (כולל השוואת Booking ו-Agoda).
- **WeasyPrint**: הפקת קובץ PDF מעוצב בעברית עם קישורי ניווט ב-Google Maps.
- **Redis**: ניהול Sessions והיסטוריית שיחה.
- **Human-in-the-loop**: הקפאת בוט והעברה לסוכן אנושי.

## משתני סביבה נדרשים (Railway / .env)
- `GEMINI_API_KEY`
- `SERPAPI_API_KEY`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `AGENT_PHONE_NUMBER`
- `REDIS_URL`
