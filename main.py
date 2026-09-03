import io
import json
import os
from datetime import date
import requests
import uvicorn
from fastapi import FastAPI, Request, Query, Response, BackgroundTasks, status
from fastapi.responses import PlainTextResponse
from google import genai
from google.genai import types
import redis
from weasyprint import HTML

from pydantic_models import (
    ClientTravelRequirements,
    TripItinerary,
    TriageResult,
    generate_maps_url
)

app = FastAPI(title="YB Travel Agent API - Gemini Powered")

# אתחול לקוחות ומשתני סביבה
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

SERPAPI_KEY = os.environ.get("SERPAPI_API_KEY", "")
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "yb_travel_secret_token_2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
AGENT_PHONE_NUMBER = os.environ.get("AGENT_PHONE_NUMBER", "")

SESSION_TTL = 48 * 3600  # 48 שעות תוקף לשיחה

# --- מנהל Session ב-Redis ---

class SessionManager:
    @staticmethod
    def get(phone: str) -> dict:
        data = redis_client.get(f"travel_session:{phone}")
        if data:
            return json.loads(data)
        return {
            "current_itinerary": None,
            "flights_data": [],
            "hotels_data": [],
            "is_human_takeover": False
        }

    @staticmethod
    def save(phone: str, session: dict):
        redis_client.setex(f"travel_session:{phone}", SESSION_TTL, json.dumps(session, ensure_ascii=False))

# --- מנועי Google Flights ו-Google Hotels דרך SerpApi ---

def get_iata_code(city_or_country: str) -> str:
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Return ONLY the 3-letter IATA airport code for the primary airport of: {city_or_country}. Output nothing else."
        )
        return response.text.strip().upper()[:3]
    except Exception:
        return "PRG"

def search_flights_google(origin: str, destination: str, departure_date: str, adults: int = 1) -> list:
    if not SERPAPI_KEY:
        return []
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "currency": "USD",
        "hl": "en",
        "adults": adults,
        "api_key": SERPAPI_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        flight_options = data.get("best_flights", []) or data.get("other_flights", [])
        parsed = []
        for flight in flight_options[:3]:
            legs = flight.get("flights", [])
            if not legs:
                continue
            stops = len(legs) - 1
            stops_text = "טיסה ישירה" if stops == 0 else f"{stops} עצירות"
            parsed.append({
                "airline": legs[0].get("airline", "חברת תעופה"),
                "price": f"${flight.get('price', 'N/A')}",
                "departure_time": legs[0].get("departure_airport", {}).get("time", ""),
                "arrival_time": legs[-1].get("arrival_airport", {}).get("time", ""),
                "type": stops_text
            })
        return parsed
    except Exception as e:
        print(f"Error Google Flights: {e}")
        return []

def search_hotels_google(destination: str, checkin_date: str, checkout_date: str, adults: int = 2) -> list:
    if not SERPAPI_KEY:
        return []
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_hotels",
        "q": f"Hotels in {destination}",
        "check_in_date": checkin_date,
        "check_out_date": checkout_date,
        "adults": adults,
        "currency": "USD",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        parsed = []
        for h in data.get("properties", [])[:3]:
            stars = h.get("extracted_hotel_class", h.get("hotel_class", ""))
            b_price, a_price = None, None
            for p in h.get("prices", []):
                src = p.get("source", "").lower()
                if "booking" in src and not b_price:
                    b_price = p.get("rate_per_night", {}).get("lowest")
                elif "agoda" in src and not a_price:
                    a_price = p.get("rate_per_night", {}).get("lowest")

            parsed.append({
                "name": h.get("name", "מלון"),
                "stars": f"{stars} כוכבים" if stars else "",
                "rating": f"ציון {h.get('overall_rating', '')}" if h.get("overall_rating") else "",
                "lowest_price": h.get("rate_per_night", {}).get("lowest", "N/A"),
                "booking_price": b_price,
                "agoda_price": a_price
            })
        return parsed
    except Exception as e:
        print(f"Error Google Hotels: {e}")
        return []

# --- שליחת הודעות ומסמכים בוואטסאפ (Meta Cloud API) ---

def send_whatsapp_text(to_phone: str, text: str):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print(f"[LOCAL LOG to {to_phone}]: {text}")
        return
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": True, "body": text}
    }
    requests.post(url, json=payload, headers=headers, timeout=10)

def mark_message_as_read(message_id: str):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    requests.post(url, json=payload, headers=headers, timeout=5)

def download_and_transcribe_audio_gemini(media_id: str) -> str:
    """
    מורידה את קובץ האודיו מוואטסאפ ומעבירה אותו ישירות ל-Gemini לתמלול
    """
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta_url = f"https://graph.facebook.com/v20.0/{media_id}"
    res = requests.get(meta_url, headers=headers, timeout=10).json()
    download_url = res.get("url")

    audio_bytes = requests.get(download_url, headers=headers, timeout=15).content

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type="audio/ogg"
            ),
            "תמלל במדויק מילה במילה את ההקלטה הקולית הזו לעברית. החזר אך ורק את הטקסט המתומלל ללא שום הקדמות או תוספות."
        ]
    )
    return response.text.strip()

def upload_and_send_pdf(to_phone: str, pdf_bytes: io.BytesIO, filename: str, caption: str):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print(f"[LOCAL LOG] PDF generated ({len(pdf_bytes.getvalue())} bytes) for {to_phone}")
        return

    upload_url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/media"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {"file": (filename, pdf_bytes.getvalue(), "application/pdf")}
    data = {"messaging_product": "whatsapp", "type": "application/pdf"}

    up_res = requests.post(upload_url, headers=headers, files=files, data=data, timeout=25)
    up_res.raise_for_status()
    media_id = up_res.json().get("id")

    msg_url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": caption
        }
    }
    requests.post(msg_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}, json=payload, timeout=10)

# --- הפקת מסמך PDF מסכם ---

def build_pdf_document(itinerary: TripItinerary, flights: list, hotels: list) -> io.BytesIO:
    today_str = date.today().strftime('%d/%m/%Y')

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&display=swap');
            body {{
                font-family: 'Assistant', 'DejaVu Sans', sans-serif;
                margin: 25px;
                color: #222;
                background-color: #ffffff;
                line-height: 1.4;
                font-size: 13px;
            }}
            .header {{
                border-bottom: 2px solid #0056b3;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .header h1 {{
                color: #0056b3;
                margin: 0 0 5px 0;
                font-size: 22px;
            }}
            .header p {{
                color: #666;
                margin: 0;
                font-size: 13px;
            }}
            .section-title {{
                font-size: 16px;
                font-weight: bold;
                color: #0056b3;
                border-bottom: 1px solid #ddd;
                padding-bottom: 4px;
                margin-top: 18px;
                margin-bottom: 10px;
            }}
            .card {{
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 5px;
                padding: 10px 12px;
                margin-bottom: 8px;
            }}
            .card-title {{
                font-weight: bold;
                font-size: 14px;
                color: #111;
            }}
            .price-tag {{
                font-weight: bold;
                color: #28a745;
            }}
            .day-box {{
                margin-bottom: 15px;
                padding-bottom: 12px;
                border-bottom: 1px dashed #ccc;
            }}
            .day-title {{
                font-size: 15px;
                font-weight: bold;
                color: #222;
                margin-bottom: 4px;
            }}
            .maps-link {{
                display: inline-block;
                margin-top: 6px;
                color: #0056b3;
                text-decoration: none;
                font-weight: bold;
                font-size: 12px;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 11px;
                color: #777;
                border-top: 1px solid #eee;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>תוכנית טיול והצעת מחיר - {itinerary.destination}</h1>
            <p>תאריך הפקה: {today_str} | סוכנות נסיעות YB Designs</p>
        </div>
    """

    if flights:
        html += '<div class="section-title">✈️ טיסות מומלצות (Google Flights)</div>'
        for f in flights:
            html += f"""
            <div class="card">
                <div class="card-title">{f['airline']} ({f['type']})</div>
                <div>שעות: {f['departure_time']} ⬅️ {f['arrival_time']}</div>
                <div class="price-tag">מחיר: {f['price']} לאדם</div>
            </div>
            """

    if hotels:
        html += '<div class="section-title">🏨 מלונות מומלצים (השוואת Booking / Agoda)</div>'
        for h in hotels:
            sub = []
            if h.get("booking_price"):
                sub.append(f"Booking: {h['booking_price']}")
            if h.get("agoda_price"):
                sub.append(f"Agoda: {h['agoda_price']}")
            sub_text = f"({' | '.join(sub)})" if sub else ""
            html += f"""
            <div class="card">
                <div class="card-title">{h['name']} {h['stars']} {h['rating']}</div>
                <div class="price-tag">החל מ: {h['lowest_price']} ללילה {sub_text}</div>
            </div>
            """

    html += '<div class="section-title">🗺️ מסלול יומי מפורט ועלויות</div>'
    for day in itinerary.days:
        map_html = f'<a class="maps-link" href="{day.maps_url}">📍 פתיחת מסלול ניווט ב-Google Maps</a>' if day.maps_url else ''
        html += f"""
        <div class="day-box">
            <div class="day-title">יום {day.day_number}: {day.title}</div>
            <div>{day.summary}</div>
            <div style="margin: 4px 0;"><strong>ציר התחנות:</strong> {day.origin} ⬅️ {' ⬅️ '.join(day.stops)} ⬅️ {day.destination}</div>
            <div class="price-tag">עלות יומית מוערכת לאדם: {day.daily_cost_estimate:.0f} {itinerary.currency}</div>
            {map_html}
        </div>
        """

    html += """
        <div class="footer">
            הופק באמצעות סוכן הנסיעות הדיגיטלי | המחירים נדגמו בזמן אמת וכפופים לזמינות בעת הכרטוס
        </div>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- לוגיקת סוכן ה-AI מבוסס Gemini עם Structured Outputs ---

def check_human_handoff(text: str) -> tuple[bool, str]:
    explicit_kws = ["נציג", "אדם", "סוכן אמיתי", "בן אדם", "תעביר אותי", "שירות לקוחות", "לדבר עם מישהו"]
    for kw in explicit_kws:
        if kw in text:
            return True, f"בקשת נציג מפורשת: '{kw}'"

    system_instruction = """
    אתה מנתח שיחות עבור שירות לקוחות של סוכנות נסיעות.
    זהה האם הודעת הלקוח מביעה כעס קיצוני, תסכול עמוק מהבוט, בקשה מורכבת שחורגת מתכנון טיול רגיל, או דרישה חד-משמעית לטיפול אנושי.
    היה רגיש לתסכול והעבר לנציג אנושי בכל מקרה של ספק.
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=TriageResult
            )
        )
        res: TriageResult = response.parsed
        return res.needs_human, res.reason
    except Exception:
        return False, ""

def extract_requirements(raw_text: str) -> ClientTravelRequirements:
    today_str = date.today().isoformat()
    system_instruction = f"""
    אתה עוזר מומחה לסוכן נסיעות. תפקידך לחלץ דרישות טיול מדויקות מתוך פניית לקוח ולמלא את סכמת ה-Pydantic.
    
    עקרונות חילוץ קריטיים:
    1. תאריך הייחוס של היום הוא {today_str}. השתמש בו לפענוח תאריכים יחסיים (למשל 'שבוע הבא', 'באוקטובר', 'בחגים').
    2. ברירות מחדל חכמות: אם הלקוח לא ציין תקציב יומי, הגדר 80 במטבע USD. אם לא צוין קצב, הגדר 'moderate'.
    3. זהה במדויק אילוצי כשרות, שבת, עגלת תינוק, והרכב נוסעים מדויק.
    """
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=raw_text,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=ClientTravelRequirements
        )
    )
    return response.parsed

def build_itinerary(req: ClientTravelRequirements) -> TripItinerary:
    system_instruction = """
    אתה מתכנן טיולים ומומחה גאוגרפי בינלאומי בעל שם עולמי עבור סוכנות נסיעות מובילה.
    תפקידך לתכנן תוכנית טיול מפורטת, ישימה ואיכותית לפי דרישות הלקוח.

    עקרונות תכנון חובה:
    1. הגיון גאוגרפי מוחלט: סדר את התחנות בכל יום בציר תנועה רציף אחד (Cluster) כדי למנוע הליכה או נסיעה מיותרת הלוך ושוב.
    2. עלות יומית מוערכת לאדם (daily_cost_estimate): חשב עלות ריאלית לכל יום בנפרד (ארוחות, כניסות לאתרים, תחבורה מקומית) במסגרת תקציב הלקוח.
    3. דיוק שמות: רשום את שמות האתרים באנגלית תקנית או בשפת המקור כדי שזיהוי המיקום ב-Google Maps יהיה מדויק ללא שגיאות.
    4. התאמה לאילוצים: הקפד על אילוצי נגישות, קצב הליכה, והרכב המשפחה.
    """

    user_prompt = f"בנה תוכנית טיול מלאה על פי הדרישות הבאות:\n{req.model_dump_json(indent=2)}"

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=TripItinerary
        )
    )
    itinerary: TripItinerary = response.parsed
    for day in itinerary.days:
        day.maps_url = generate_maps_url(day.origin, day.stops, day.destination, day.travel_mode)
    return itinerary

def update_itinerary(current_itinerary: dict, feedback: str) -> TripItinerary:
    system_instruction = """
    אתה מתכנן טיולים בכיר. קיבלת תוכנית טיול קיימת ובקשת שינוי או דיוק מלקוח.
    
    עקרונות עבודה:
    1. עדכן אך ורק את הימים או הרכיבים הספציפיים שהלקוח ביקש לשנות, ושמור על שאר התוכנית המקורית יציבה לחלוטין.
    2. ודא כי התחנות החדשות שומרות על רצף גאוגרפי הגיוני.
    3. חשב מחדש את העלות היומית המוערכת (daily_cost_estimate) עבור הימים שעודכנו.
    """

    user_prompt = f"""
    המסלול הקיים:
    {json.dumps(current_itinerary, ensure_ascii=False, indent=2)}

    בקשת השינוי של הלקוח:
    "{feedback}"
    """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=TripItinerary
        )
    )
    itinerary: TripItinerary = response.parsed
    for day in itinerary.days:
        day.maps_url = generate_maps_url(day.origin, day.stops, day.destination, day.travel_mode)
    return itinerary

# --- משימת הרקע הראשית ---

def process_interaction_task(sender_phone: str, msg_type: str, msg_data: dict):
    try:
        msg_id = msg_data.get("id")
        if msg_id:
            mark_message_as_read(msg_id)

        raw_text_incoming = msg_data.get("text", {}).get("body", "").strip() if msg_type == "text" else ""

        # פקודת שחרור בוט על ידי סוכן
        if sender_phone == AGENT_PHONE_NUMBER and raw_text_incoming.startswith("/resume"):
            parts = raw_text_incoming.split()
            if len(parts) > 1:
                target_phone = parts[1]
                t_session = SessionManager.get(target_phone)
                t_session["is_human_takeover"] = False
                SessionManager.save(target_phone, t_session)
                send_whatsapp_text(AGENT_PHONE_NUMBER, f"✅ הבוט הופשר בהצלחה עבור {target_phone}")
                send_whatsapp_text(target_phone, "השיחה חזרה למענה האוטומטי. נשמח להמשיך לסייע בתכנון החופשה! 🌍")
            return

        session = SessionManager.get(sender_phone)
        if session.get("is_human_takeover", False):
            return

        # מענה מידי ללקוח
        if msg_type == "audio":
            send_whatsapp_text(sender_phone, "היי! קיבלנו את ההקלטה שלך 🎧 מתמללים את הבקשה, בודקים טיסות ומלונות ומכינים עבורך קובץ הצעה מסודר...")
            user_text = download_and_transcribe_audio_gemini(msg_data.get("audio", {}).get("id"))
        else:
            send_whatsapp_text(sender_phone, "היי! קיבלנו את הבקשה ✈️ כבר בודקים טיסות, מלונות ומפיקים עבורך מסמך טיול אישי ומפורט...")
            user_text = raw_text_incoming

        if not user_text:
            return

        # בדיקת צורך בהעברה לנציג אנושי
        needs_human, reason = check_human_handoff(user_text)
        if needs_human:
            session["is_human_takeover"] = True
            SessionManager.save(sender_phone, session)
            send_whatsapp_text(
                AGENT_PHONE_NUMBER,
                f"🚨 *התראת העברה לנציג אנושי!*\nלקוח: wa.me/{sender_phone}\nסיבה: {reason}\nהודעה: \"{user_text}\"\nלשחרור: /resume {sender_phone}"
            )
            send_whatsapp_text(sender_phone, "העברתי את השיחה ישירות לסוכן נסיעות אנושי מצוות המשרד. 🙋‍♂️ ניכנס לשיחה בהקדם!")
            return

        # ניתוב: עדכון מסלול קיים או יצירת טיול חדש
        if session.get("current_itinerary"):
            itinerary = update_itinerary(session["current_itinerary"], user_text)
            flights = session.get("flights_data", [])
            hotels = session.get("hotels_data", [])
        else:
            req = extract_requirements(user_text)
            itinerary = build_itinerary(req)

            # איתור טיסות ומלונות דרך SerpApi
            dest_iata = get_iata_code(req.trip_overview.destination)
            flights = search_flights_google(
                origin="TLV",
                destination=dest_iata,
                departure_date=str(req.trip_overview.start_date),
                adults=req.travelers.adults_count
            )
            hotels = search_hotels_google(
                destination=req.trip_overview.destination,
                checkin_date=str(req.trip_overview.start_date),
                checkout_date=str(req.trip_overview.end_date),
                adults=req.travelers.adults_count
            )

            session["flights_data"] = flights
            session["hotels_data"] = hotels

        session["current_itinerary"] = itinerary.model_dump()
        SessionManager.save(sender_phone, session)

        # הפקת קובץ PDF מעוצב
        pdf_file = build_pdf_document(itinerary, flights, hotels)
        filename = f"Trip_Plan_{itinerary.destination}.pdf"

        # הודעת סיכום ומסמך מצורף
        whatsapp_summary = (
            f"✈️ *תוכנית הטיול שלך ל{itinerary.destination} מוכנה!*\n\n"
            f"הכנתי עבורכם מסמך מסכם הכולל:\n"
            f"• אפשרויות טיסה ומלונות מובילים (Booking / Agoda)\n"
            f"• מסלול יומי עם עלויות יומיות משוערכות\n"
            f"• קישורים ישירים לניווט ב-Google Maps\n\n"
            f"📄 המסמך המלא מצורף כאן למטה לנוחיותכם. אשמח לשמוע מה דעתכם!"
        )
        send_whatsapp_text(sender_phone, whatsapp_summary)
        upload_and_send_pdf(sender_phone, pdf_file, filename, f"הצעת מחיר ותוכנית טיול - {itinerary.destination}")

    except Exception as e:
        print(f"Error handling interaction: {e}")
        send_whatsapp_text(sender_phone, "היי, התחלנו לעבד את הבקשה אך חסרים לנו מעט פרטים (יעד או תאריכים). נשמח לפירוט קצר כדי שנוכל להשלים את התוכנית.")

# --- Endpoints של השרת ---

@app.get("/")
def root():
    return {
        "status": "online",
        "engine": "Google Gemini 2.5 Flash",
        "service": "YB Travel Agent API"
    }

@app.get("/webhook")
def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_403_FORBIDDEN)

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            msg_type = msg.get("type")
            sender_phone = msg.get("from")
            if msg_type in ["text", "audio"]:
                background_tasks.add_task(
                    process_interaction_task,
                    sender_phone=sender_phone,
                    msg_type=msg_type,
                    msg_data=msg
                )
    except (IndexError, KeyError):
        pass
    return Response(status_code=status.HTTP_200_OK)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
