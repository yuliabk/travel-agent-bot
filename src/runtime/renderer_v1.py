"""Render Contract v1 proposal drafts without creating new commercial facts."""

from __future__ import annotations

from src.contracts.travel_v1 import ProposalDraft, TripRequest


def _price(option: dict) -> str:
    amount = option.get("amount")
    currency = option.get("currency")
    if amount is not None and currency:
        return f"{amount} {currency} (מאומת)"

    observed_amount = option.get("observed_amount")
    observed_currency = option.get("observed_currency")
    if observed_amount is not None and observed_currency:
        return f"{observed_amount} {observed_currency} (נצפה בחיפוש, לא מאומת להזמנה)"

    display = option.get("price_display")
    if display:
        return f"{display} (נצפה בחיפוש, לא מאומת להזמנה)"
    return "מחיר לא מאומת"


def render_ai_draft_hebrew(request: TripRequest, proposal: ProposalDraft) -> str:
    lines = [
        "# ⚠️ טיוטת AI - נדרש אישור סוכן",
        "",
        f"**יעד:** {request.destination}",
        f"**תאריכים:** {request.departure_date.isoformat()} עד {request.return_date.isoformat()}",
        f"**נוסעים:** {request.travelers.adults} מבוגרים, {len(request.travelers.children)} ילדים",
        "",
    ]

    if proposal.summary:
        lines.extend(["## סקירת הטיול", proposal.summary, ""])

    lines.append("## ✈️ אפשרויות טיסה מבוססות Evidence")
    if proposal.flight_options:
        for option in proposal.flight_options:
            segments = option.get("segments") or []
            segment_airline = (
                segments[0].get("airline")
                if segments and isinstance(segments[0], dict)
                else None
            )
            airline = option.get("carrier") or segment_airline or "טיסה"
            lines.extend(
                [
                    f"- **{airline}** - {_price(option)}",
                    f"  - סטטוס Evidence: `{option.get('price_status') or option.get('source_status', '')}`",
                    f"  - מקור: `{option.get('provider', '')}`",
                    f"  - Evidence: `{option.get('evidence_id', '')}`",
                    f"  - זמן חיפוש: {option.get('searched_at', '')}",
                ]
            )
            if option.get("departure") or option.get("arrival"):
                lines.append(
                    f"  - מסלול: {option.get('departure') or ''} → {option.get('arrival') or ''}"
                )
            if option.get("duration"):
                lines.append(f"  - משך: {option.get('duration')}")
            if option.get("stops") is not None:
                lines.append(f"  - עצירות: {option.get('stops')}")
            if option.get("price_status") == "observed":
                lines.append("  - ⚠️ יש לאמת מחיר וזמינות לפני הזמנה או כרטוס.")
    else:
        lines.append("- אין כרגע מחיר טיסה מאומת או אפשרות טיסה נצפית להצגה.")
    lines.append("")

    lines.append("## 🏨 אפשרויות מלון מבוססות Evidence")
    if proposal.hotel_options:
        for option in proposal.hotel_options:
            lines.extend(
                [
                    f"- **{option.get('name') or 'מלון'}** - {_price(option)} ({option.get('price_basis') or 'בסיס מחיר לא ידוע'})",
                    f"  - מקור: `{option.get('provider', '')}`",
                    f"  - Evidence: `{option.get('evidence_id', '')}`",
                    f"  - זמן חיפוש: {option.get('searched_at', '')}",
                ]
            )
    else:
        lines.append("- אין כרגע מחיר מלון מאומת להצגה.")
    lines.append("")

    if proposal.daily_itinerary:
        lines.append("## 🗺️ מסלול מוצע")
        for day in proposal.daily_itinerary:
            lines.append(
                f"### יום {day.get('day_number', '')}: {day.get('title', '')}"
            )
            if day.get("summary"):
                lines.append(str(day["summary"]))
            for place in day.get("suggested_places", []) or []:
                lines.append(f"- [[{place}]]")
            lines.append("")

    if proposal.assumptions:
        lines.append("## הנחות")
        lines.extend([f"- {item}" for item in proposal.assumptions])
        lines.append("")

    if proposal.warnings:
        lines.append("## חשוב לדעת")
        lines.extend([f"- {item}" for item in proposal.warnings])
        lines.append("")

    lines.extend(
        [
            "---",
            "**סטטוס:** טיוטת AI בלבד. Evidence נצפה אינו הבטחת מחיר או זמינות; הצעה סופית מחייבת אימות ואישור סוכן אנושי.",
        ]
    )
    return "\n".join(lines)
