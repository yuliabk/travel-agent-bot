"""
External travel tools: flight/hotel search via SerpApi and PDF generation.

Extracted from the original monolithic ``main.py`` so every channel shares the
exact same logic through the agent core. All network calls are defensive: a
failure returns an empty result instead of raising, so a single flaky upstream
never crashes a whole request.
"""

import io
from datetime import date
from typing import List, Optional

import requests

from pydantic_models import TripItinerary
from . import config
from .logger import get_logger

logger = get_logger("travel_tools")

SERPAPI_URL = "https://serpapi.com/search"


def get_iata_code(ai_client, city_or_country: str) -> str:
    """Resolve the primary IATA airport code for a city/country via Gemini."""
    if not ai_client or not city_or_country:
        return config.DEFAULT_ORIGIN_IATA
    try:
        response = ai_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=(
                "Return ONLY the 3-letter IATA airport code for the primary "
                f"airport of: {city_or_country}. Output nothing else."
            ),
        )
        code = (response.text or "").strip().upper()[:3]
        return code or config.DEFAULT_ORIGIN_IATA
    except Exception as exc:
        logger.warning("get_iata_code failed for '%s': %s", city_or_country, exc)
        return config.DEFAULT_ORIGIN_IATA


def search_flights_google(origin: str, destination: str, departure_date: str, adults: int = 1) -> List[dict]:
    if not config.SERPAPI_KEY:
        logger.info("SERPAPI key missing - skipping flight search")
        return []
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "currency": "USD",
        "hl": "en",
        "adults": adults,
        "type": 2,  # one-way; avoids SerpApi requiring a return date
        "api_key": config.SERPAPI_KEY,
    }
    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
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
            parsed.append(
                {
                    "airline": legs[0].get("airline", "חברת תעופה"),
                    "price": f"${flight.get('price', 'N/A')}",
                    "departure_time": legs[0].get("departure_airport", {}).get("time", ""),
                    "arrival_time": legs[-1].get("arrival_airport", {}).get("time", ""),
                    "type": stops_text,
                }
            )
        return parsed
    except Exception as exc:
        logger.error("Google Flights search failed: %s", exc)
        return []


def search_hotels_google(destination: str, checkin_date: str, checkout_date: str, adults: int = 2) -> List[dict]:
    if not config.SERPAPI_KEY:
        logger.info("SERPAPI key missing - skipping hotel search")
        return []
    params = {
        "engine": "google_hotels",
        "q": f"Hotels in {destination}",
        "check_in_date": checkin_date,
        "check_out_date": checkout_date,
        "adults": adults,
        "currency": "USD",
        "hl": "en",
        "api_key": config.SERPAPI_KEY,
    }
    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
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
            parsed.append(
                {
                    "name": h.get("name", "מלון"),
                    "stars": f"{stars} כוכבים" if stars else "",
                    "rating": f"ציון {h.get('overall_rating', '')}" if h.get("overall_rating") else "",
                    "lowest_price": h.get("rate_per_night", {}).get("lowest", "N/A"),
                    "booking_price": b_price,
                    "agoda_price": a_price,
                }
            )
        return parsed
    except Exception as exc:
        logger.error("Google Hotels search failed: %s", exc)
        return []


def build_pdf_document(itinerary: TripItinerary, flights: list, hotels: list) -> Optional[io.BytesIO]:
    """Render the itinerary + offers into a styled Hebrew (RTL) PDF.

    Returns ``None`` if WeasyPrint is unavailable or rendering fails, so callers
    can gracefully fall back to a text-only reply.
    """
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.error("WeasyPrint unavailable - cannot build PDF: %s", exc)
        return None

    today_str = date.today().strftime("%d/%m/%Y")

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&display=swap');
            body {{ font-family: 'Assistant', 'DejaVu Sans', sans-serif; margin: 25px; color: #222; background:#fff; line-height:1.4; font-size:13px; }}
            .header {{ border-bottom: 2px solid #0056b3; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h1 {{ color: #0056b3; margin: 0 0 5px 0; font-size: 22px; }}
            .header p {{ color: #666; margin: 0; font-size: 13px; }}
            .section-title {{ font-size: 16px; font-weight: bold; color: #0056b3; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-top: 18px; margin-bottom: 10px; }}
            .card {{ background:#f8f9fa; border:1px solid #e9ecef; border-radius:5px; padding:10px 12px; margin-bottom:8px; }}
            .card-title {{ font-weight: bold; font-size: 14px; color: #111; }}
            .price-tag {{ font-weight: bold; color: #28a745; }}
            .day-box {{ margin-bottom: 15px; padding-bottom: 12px; border-bottom: 1px dashed #ccc; }}
            .day-title {{ font-size: 15px; font-weight: bold; color: #222; margin-bottom: 4px; }}
            .maps-link {{ display:inline-block; margin-top:6px; color:#0056b3; text-decoration:none; font-weight:bold; font-size:12px; }}
            .footer {{ margin-top: 30px; text-align:center; font-size: 11px; color: #777; border-top: 1px solid #eee; padding-top: 10px; }}
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
        map_html = (
            f'<a class="maps-link" href="{day.maps_url}">📍 פתיחת מסלול ניווט ב-Google Maps</a>' if day.maps_url else ""
        )
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

    try:
        pdf_buffer = io.BytesIO()
        HTML(string=html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as exc:
        logger.error("PDF rendering failed: %s", exc)
        return None
