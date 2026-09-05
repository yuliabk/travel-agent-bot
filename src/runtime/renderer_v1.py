"""Readable Hebrew output with explicitly scoped provider-based cost estimates."""
from datetime import date
from decimal import Decimal, InvalidOperation
from src.contracts.travel_v1 import ProposalDraft, TripRequest


def amount(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def money(value, currency):
    number = amount(value)
    unit = {'ILS': '₪', 'USD': '$', 'EUR': '€', 'PLN': 'זלוטי'}.get(currency, currency)
    return f'{number:,.2f} {unit}' if number is not None and currency else 'טרם תומחר'


def clean(value):
    return str(value or '').replace('|', ' / ').replace('\n', ' ')


def destination_label(value):
    return {'Wroclaw, Poland': 'ורוצלב, פולין', 'Krakow, Poland': 'קרקוב, פולין', 'Warsaw, Poland': 'ורשה, פולין', 'Poznan, Poland': 'פוזנן, פולין', 'Katowice, Poland': 'קטוביץ, פולין'}.get(value, value)


MESSAGES = {
    'No verified flight price is available.': 'לא נמצא מחיר טיסה מאומת לתאריכים שבחרתם.',
    'No verified hotel price is available.': 'לא נמצא מחיר לינה מאומת לתאריכים שבחרתם.',
    'No aggregate trip total is computed because provider pricing bases may differ.': 'מחירי חלופות אינם מתחברים זה לזה. עלות הטיול המלאה תיקבע לאחר בחירת טיסה, חדר ותוספות.',
    'Daily itinerary content is an AI planning suggestion unless separately backed by place evidence.': 'המסלול הוא הצעה לתכנון. יש לבדוק שעות פתיחה, מזג אוויר וזמינות לפני הביקור.',
    'Live commercial evidence search failed; commercial results may be incomplete.': 'חיפוש המחירים לא הושלם. נסו שוב כדי לקבל מחירים עדכניים.',
    'Live commercial evidence search was not executed.': 'חיפוש מחירים לא בוצע, ולכן אין עדיין תמחור לטיול.',
    'Planner model failed; returning an evidence-only partial draft.': 'יצירת המסלול לא הושלמה. מוצגים רק פרטי המחירים שנמצאו; נסו ליצור מסלול מחדש.',
}


def render_ai_draft_hebrew(request: TripRequest, proposal: ProposalDraft) -> str:
    nights = (request.return_date - request.departure_date).days
    destination = destination_label(request.destination)
    lines = ['# תוכנית הטיול שלכם', '', f'**יעד:** {destination}',
             f'**תאריכים:** {request.departure_date:%d/%m/%Y} עד {request.return_date:%d/%m/%Y} · {nights + 1} ימים, {nights} לילות',
             f'**נוסעים:** {request.travelers.adults} מבוגרים, {len(request.travelers.children)} ילדים',
             f'**התקציב שהגדרתם:** {money(request.budget, request.currency)}', '']
    if proposal.summary:
        lines += ['## מבט על הטיול', proposal.summary, '']
    if request.arrival_airport:
        lines += [f'**שדה נחיתה שנבחר:** {request.arrival_airport}. מקומות הלינה נקבעים בנפרד.', '']
    lines += ['## פירוט עלויות לינה', 'בוחרים חלופת מלון אחת בכל מקום לינה. אין לחבר חלופות לאותו מקטע.', '']
    segments = request.stays or [None]
    segment_totals = []
    for index, stay in enumerate(segments):
        segment_nights = (stay.check_out - stay.check_in).days if stay else nights
        label = destination_label(stay.destination) if stay else destination
        if stay:
            lines += [f'### לינה {index + 1}: {label}', f'{stay.check_in:%d/%m/%Y} עד {stay.check_out:%d/%m/%Y} · {segment_nights} לילות']
        hotels = [hotel for hotel in proposal.hotel_options if hotel.get('stay_index', 0) == index][:3 if stay else 5]
        lines += ['| מלון | מחיר ללילה | עלות למקטע הלינה | אופן החישוב |', '| --- | --- | --- | --- |']
        totals = {}
        for hotel in hotels:
            nightly = amount(hotel.get('amount'))
            total = amount(hotel.get('stay_total'))
            basis = 'מחיר לשהות שנמסר מהספק'
            if total is None and nightly is not None and hotel.get('price_basis') == 'per_night' and segment_nights > 0:
                total = nightly * segment_nights
                basis = f"אומדן: {money(nightly, hotel.get('currency'))} × {segment_nights} לילות"
            currency = hotel.get('currency')
            if total is not None and currency:
                totals[currency] = min(totals.get(currency, total), total)
            lines.append(f"| {clean(hotel.get('name') or 'מלון')} | {money(nightly, currency)} | {money(total, currency)} | {basis if total is not None else 'בסיס המחיר דורש בירור'} |")
        if not hotels:
            lines.append('| לא נמצא מחיר למקום לינה זה | טרם תומחר | טרם תומחר | דרוש חיפוש נוסף |')
        segment_totals.append((label, totals))
        lines.append('')
    lines += ['המחירים מתייחסים לאפשרות הלינה שהחזיר החיפוש. יש לאשר מספר חדרים, התאמה לכל הנוסעים, מסים ותנאי ביטול. אין להכפיל מחיר במספר הנוסעים ללא בדיקת תפוסת החדר.', '', '## אפשרויות טיסה']
    primary = [flight for flight in proposal.flight_options if not flight.get('alternative')]
    alternatives = [flight for flight in proposal.flight_options if flight.get('alternative')]
    def flight_line(flight):
        legs = flight.get('segments') or []
        airline = legs[0].get('airline') if legs else 'טיסה'
        code = flight.get('arrival_iata') or ''
        exceeds = flight.get('currency') == request.currency and amount(flight.get('amount')) is not None and amount(flight.get('amount')) > request.budget
        return f"- **{clean(airline or 'טיסה')}:** {money(flight.get('amount'), flight.get('currency'))} — נחיתה ב־{code}. יש לאשר הלוך וחזור, מספר נוסעים וכבודה." + (' מחיר הטיסה לבדו חורג מהתקציב שהוגדר.' if exceeds else '')
    lines += [flight_line(flight) for flight in primary[:3]]
    if not primary:
        lines.append('לא התקבל מחיר טיסה מאומת לפי הבקשה המקורית.')
    if alternatives:
        lines += ['', '## חלופות טיסה לבחירתכם', 'אלה הצעות נוספות בלבד. שדה הנחיתה שבחרתם ומקומות הלינה לא השתנו.']
        seen = set()
        for flight in alternatives:
            key = (flight.get('arrival_iata'), flight.get('alternative_note'))
            if key in seen:
                continue
            seen.add(key)
            lines += [f"**{flight.get('alternative_note') or 'חלופה'}**", flight_line(flight)]
        lines += ['עלות וזמן המעבר משדה חלופי למקום הלינה טרם אומתו ואינם כלולים במחיר הטיסה. יש לבדוק גם הגעה לשדה לטיסת החזרה.']
    lines += ['', '## סיכום התקציב', '| רכיב | סכום ומצב |', '| --- | --- |']
    for index, (label, totals) in enumerate(segment_totals):
        costs = ' / '.join(money(total, currency) for currency, total in totals.items()) or 'חסר מחיר'
        lines.append(f'| לינה {index + 1}: {clean(label)} — החל מ־ | {costs} |')
    common = set.intersection(*(set(totals) for _, totals in segment_totals)) if segment_totals else set()
    if common:
        for currency in sorted(common):
            total = sum(totals[currency] for _, totals in segment_totals)
            lines.append(f'| סך לינה לכל המקטעים — החל מ־ | {money(total, currency)}, חלופה אחת בכל מקטע ובכפוף לאישור תפוסה |')
    else:
        lines.append('| סך הלינה לכל הטיול | לא ניתן לחשב: חסר מחיר למקטע או שהמטבעות שונים |')
    lines += ['| טיסות | נדרש אישור מחיר לכל הנוסעים; לא נכלל בסכום הלינה |' if proposal.flight_options else '| טיסות | חסר מחיר |',
              '| מעברים בין מקומות הלינה ומשדה התעופה | טרם תומחרו |',
              '| אוכל, תחבורה, אטרקציות וביטוח | טרם תומחרו |',
              '| עלות כוללת לטיול | עדיין לא ניתן לחשב — חסרים רכיבים מאומתים |', '',
              '**הסכום הידוע הוא ללינה בלבד, ולא מחיר החופשה כולה.** אין עדיין אפשרות לקבוע אם הטיול עומד בתקציב.', '']
    if proposal.daily_itinerary:
        lines.append('## המסלול היומי והמפה')
        for day in proposal.daily_itinerary:
            lines += [f"### יום {day.get('day_number', '')}: {day.get('title', '')}", f"**מיקום ליום:** {day.get('location') or request.destination}", str(day.get('summary') or '')]
            lines += [f'- [[{place}]]' for place in day.get('suggested_places', []) or []]
            lines.append('')
    notes = list(dict.fromkeys(MESSAGES.get(item, item) for item in proposal.assumptions + proposal.warnings))
    if notes:
        lines += ['## לפני שמזמינים'] + [f'- {item}' for item in notes] + ['']
    lines += ['---', 'זוהי תוכנית ראשונית לבדיקה. המחירים והזמינות עשויים להשתנות; הזמנה סופית תיעשה לאחר אישור סוכן נסיעות.']
    return '\n'.join(lines)
