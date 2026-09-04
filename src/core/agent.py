"""
Unified AI agent core - the shared "brain" for every channel.

WhatsApp, Email and the Web Form all call :func:`handle_message` with a common
payload ``{channel, user_id, message, context}`` and receive an
:class:`AgentResponse`. This guarantees identical behaviour (triage, itinerary
planning, flight/hotel search, PDF generation, conversation memory) regardless
of how the request arrived.
"""
import io
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic_models import (
    ClientTravelRequirements,
    TripItinerary,
    TriageResult,
    generate_maps_url,
)
from . import config
from . import travel_tools
from .logger import get_logger
from .session import session_manager

logger = get_logger("agent")

# Explicit keywords that always force a human handoff.
_EXPLICIT_HANDOFF_KEYWORDS = [
    "נציג", "אדם", "סוכן אמיתי", "בן אדם", "תעביר אותי",
    "שירות לקוחות", "לדבר עם מישהו",
]


@dataclass
class AgentResponse:
    """Everything a channel needs to reply to the user."""

    text: str
    pdf_bytes: Optional[io.BytesIO] = None
    pdf_filename: Optional[str] = None
    handoff: bool = False
    handoff_reason: str = ""
    destination: Optional[str] = None
    error: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


class TravelAgent:
    """Wraps the Gemini client and all planning logic."""

    def __init__(self) -> None:
        self._ai_client = None
        self._init_error: Optional[str] = None
        self._init_client()

    def _init_client(self) -> None:
        if not config.GEMINI_API_KEY:
            self._init_error = "GEMINI_API_KEY is not configured"
            logger.error(self._init_error)
            return
        try:
            from google import genai

            self._ai_client = genai.Client(api_key=config.GEMINI_API_KEY)
            logger.info("Gemini client initialised (model=%s)", config.GEMINI_MODEL)
        except Exception as exc:  # pragma: no cover - depends on env
            self._init_error = f"Failed to init Gemini client: {exc}"
            logger.error(self._init_error)

    @property
    def ai_client(self):
        return self._ai_client

    # --- AI helpers -----------------------------------------------------

    def check_human_handoff(self, text: str) -> (bool, str):
        for kw in _EXPLICIT_HANDOFF_KEYWORDS:
            if kw in text:
                return True, f"בקשת נציג מפורשת: '{kw}'"
        if not self._ai_client:
            return False, ""
        system_instruction = (
            "אתה מנתח שיחות עבור שירות לקוחות של סוכנות נסיעות. "
            "זהה האם הודעת הלקוח מביעה כעס קיצוני, תסכול עמוק מהבוט, בקשה מורכבת "
            "שחורגת מתכנון טיול רגיל, או דרישה חד-משמעית לטיפול אנושי. "
            "היה רגיש לתסכול והעבר לנציג אנושי בכל מקרה של ספק."
        )
        try:
            from google.genai import types

            response = self._ai_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TriageResult,
                ),
            )
            res: TriageResult = response.parsed
            if res is None:
                return False, ""
            return res.needs_human, res.reason
        except Exception as exc:
            logger.warning("Triage check failed: %s", exc)
            return False, ""

    def extract_requirements(self, raw_text: str) -> Optional[ClientTravelRequirements]:
        if not self._ai_client:
            return None
        from google.genai import types

        today_str = date.today().isoformat()
        system_instruction = f"""
        אתה עוזר מומחה לסוכן נסיעות. תפקידך לחלץ דרישות טיול מדויקות מתוך פניית לקוח ולמלא את סכמת ה-Pydantic.

        עקרונות חילוץ קריטיים:
        1. תאריך הייחוס של היום הוא {today_str}. השתמש בו לפענוח תאריכים יחסיים (למשל 'שבוע הבא', 'באוקטובר', 'בחגים').
        2. ברירות מחדל חכמות: אם הלקוח לא ציין תקציב יומי, הגדר 80 במטבע USD. אם לא צוין קצב, הגדר 'moderate'.
        3. זהה במדויק אילוצי כשרות, שבת, עגלת תינוק, והרכב נוסעים מדויק.
        """
        try:
            response = self._ai_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=raw_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ClientTravelRequirements,
                ),
            )
            return response.parsed
        except Exception as exc:
            logger.error("extract_requirements failed: %s", exc)
            return None

    def build_itinerary(self, req: ClientTravelRequirements) -> Optional[TripItinerary]:
        if not self._ai_client:
            return None
        from google.genai import types

        system_instruction = """
        אתה מתכנן טיולים ומומחה גאוגרפי בינלאומי בעל שם עולמי עבור סוכנות נסיעות מובילה.
        תפקידך לתכנן תוכנית טיול מפורטת, ישימה ואיכותית לפי דרישות הלקוח.

        עקרונות תכנון חובה:
        1. הגיון גאוגרפי מוחלט: סדר את התחנות בכל יום בציר תנועה רציף אחד (Cluster).
        2. עלות יומית מוערכת לאדם (daily_cost_estimate): חשב עלות ריאלית לכל יום בנפרד.
        3. דיוק שמות: רשום את שמות האתרים באנגלית תקנית או בשפת המקור לזיהוי מדויק ב-Google Maps.
        4. התאמה לאילוצים: הקפד על אילוצי נגישות, קצב הליכה, והרכב המשפחה.
        """
        user_prompt = f"בנה תוכנית טיול מלאה על פי הדרישות הבאות:\n{req.model_dump_json(indent=2)}"
        try:
            response = self._ai_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TripItinerary,
                ),
            )
            itinerary: TripItinerary = response.parsed
            if itinerary is None:
                return None
            for day in itinerary.days:
                day.maps_url = generate_maps_url(day.origin, day.stops, day.destination, day.travel_mode)
            return itinerary
        except Exception as exc:
            logger.error("build_itinerary failed: %s", exc)
            return None

    def update_itinerary(self, current_itinerary: dict, feedback: str) -> Optional[TripItinerary]:
        if not self._ai_client:
            return None
        from google.genai import types

        system_instruction = """
        אתה מתכנן טיולים בכיר. קיבלת תוכנית טיול קיימת ובקשת שינוי או דיוק מלקוח.

        עקרונות עבודה:
        1. עדכן אך ורק את הימים או הרכיבים הספציפיים שהלקוח ביקש לשנות.
        2. ודא כי התחנות החדשות שומרות על רצף גאוגרפי הגיוני.
        3. חשב מחדש את העלות היומית המוערכת (daily_cost_estimate) עבור הימים שעודכנו.
        """
        user_prompt = f"""
        המסלול הקיים:
        {json.dumps(current_itinerary, ensure_ascii=False, indent=2)}

        בקשת השינוי של הלקוח:
        "{feedback}"
        """
        try:
            response = self._ai_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TripItinerary,
                ),
            )
            itinerary: TripItinerary = response.parsed
            if itinerary is None:
                return None
            for day in itinerary.days:
                day.maps_url = generate_maps_url(day.origin, day.stops, day.destination, day.travel_mode)
            return itinerary
        except Exception as exc:
            logger.error("update_itinerary failed: %s", exc)
            return None

    # --- Main entry point ----------------------------------------------

    def handle_message(
        self,
        channel: str,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process one inbound message from any channel and return a response."""
        context = context or {}
        message = (message or "").strip()

        if not self._ai_client:
            return AgentResponse(
                text="השירות אינו זמין כרגע (חסר מפתח AI). נסו שוב מאוחר יותר.",
                error=True,
            )
        if not message:
            return AgentResponse(
                text="לא זוהה תוכן בבקשה. נשמח שתכתבו לנו יעד ותאריכים משוערים.",
                error=True,
            )

        session = session_manager.get(channel, user_id)
        session_manager.append_history(session, "user", message)

        # 1) Human takeover already active -> stay silent for automated reply.
        if session.get("is_human_takeover", False):
            session_manager.save(channel, user_id, session)
            return AgentResponse(text="", meta={"suppressed": True, "reason": "human_takeover"})

        # 2) Triage - does this need a human?
        needs_human, reason = self.check_human_handoff(message)
        if needs_human:
            session["is_human_takeover"] = True
            session_manager.save(channel, user_id, session)
            return AgentResponse(
                text="העברתי את השיחה ישירות לסוכן נסיעות אנושי מצוות המשרד. 🙋‍♂️ ניכנס לשיחה בהקדם!",
                handoff=True,
                handoff_reason=reason,
            )

        # 3) Plan or update the itinerary.
        try:
            if session.get("current_itinerary"):
                itinerary = self.update_itinerary(session["current_itinerary"], message)
                flights = session.get("flights_data", [])
                hotels = session.get("hotels_data", [])
            else:
                req = self.extract_requirements(message)
                if req is None:
                    return AgentResponse(
                        text=(
                            "התחלנו לעבד את הבקשה אך חסרים לנו מעט פרטים (יעד או תאריכים). "
                            "נשמח לפירוט קצר כדי שנוכל להשלים את התוכנית."
                        ),
                        error=True,
                    )
                itinerary = self.build_itinerary(req)
                dest_iata = travel_tools.get_iata_code(self._ai_client, req.trip_overview.destination)
                flights = travel_tools.search_flights_google(
                    origin=config.DEFAULT_ORIGIN_IATA,
                    destination=dest_iata,
                    departure_date=str(req.trip_overview.start_date),
                    adults=req.travelers.adults_count,
                )
                hotels = travel_tools.search_hotels_google(
                    destination=req.trip_overview.destination,
                    checkin_date=str(req.trip_overview.start_date),
                    checkout_date=str(req.trip_overview.end_date),
                    adults=req.travelers.adults_count,
                )
                session["flights_data"] = flights
                session["hotels_data"] = hotels

            if itinerary is None:
                return AgentResponse(
                    text=(
                        "לא הצלחנו להפיק תוכנית טיול הפעם. נסו לנסח מחדש את הבקשה עם יעד "
                        "ותאריכים ברורים ונשמח לעזור."
                    ),
                    error=True,
                )

            session["current_itinerary"] = itinerary.model_dump()
            session_manager.save(channel, user_id, session)

            pdf_file = travel_tools.build_pdf_document(itinerary, flights, hotels)
            filename = f"Trip_Plan_{itinerary.destination}.pdf"

            summary = (
                f"✈️ *תוכנית הטיול שלך ל{itinerary.destination} מוכנה!*\n\n"
                f"הכנתי עבורכם מסמך מסכם הכולל:\n"
                f"• אפשרויות טיסה ומלונות מובילים (Booking / Agoda)\n"
                f"• מסלול יומי עם עלויות יומיות משוערכות\n"
                f"• קישורים ישירים לניווט ב-Google Maps\n\n"
                f"📄 המסמך המלא מצורף. אשמח לשמוע מה דעתכם!"
            )
            session_manager.append_history(session, "assistant", summary)
            session_manager.save(channel, user_id, session)

            return AgentResponse(
                text=summary,
                pdf_bytes=pdf_file,
                pdf_filename=filename,
                destination=itinerary.destination,
                meta={"flights": len(flights), "hotels": len(hotels)},
            )
        except Exception as exc:
            logger.exception("handle_message failed for %s:%s: %s", channel, user_id, exc)
            return AgentResponse(
                text=(
                    "אירעה תקלה זמנית בעיבוד הבקשה. נסו שוב בעוד רגע, ואם התקלה חוזרת "
                    "נשמח שתפרטו יעד ותאריכים."
                ),
                error=True,
            )


# Shared singleton agent used by all channels.
travel_agent = TravelAgent()
