"""Readable Hebrew output with explicitly scoped provider-based cost estimates."""
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
    destination = {'Wroclaw, Poland': 'ורוצלב, פולין'}.get(request.destination, request.destination)
    lines = ['# תוכנית הטיול שלכם', '', f'**יעד:** {destination}',
             f'**תאריכים:** {request.departure_date:%d/%m/%Y} עד {request.return_date:%d/%m/%Y} · {nights + 1} ימים, {nights} לילות',
             f'**נוסעים:** {request.travelers.adults} מבוגרים, {len(request.travelers.children)} ילדים',
             f'**התקציב שהגדרתם:** {money(request.budget, request.currency)}', '']
    if proposal.summary:
        lines += ['## מבט על הטיול', proposal.summary, '']
    lines += ['## פירוט עלויות לינה', 'כל שורה היא חלופה נפרדת. בוחרים מלון אחד; אין לחבר את מחירי המלונות.', '',
              '| מלון | מחיר ללילה | עלות לשהות | אופן החישוב |', '| --- | --- | --- | --- |']
    subtotals = []
    for hotel in proposal.hotel_options[:5]:
        nightly = amount(hotel.get('amount'))
        total = amount(hotel.get('stay_total'))
        basis = 'מחיר לשהות שנמסר מהספק'
        if total is None and nightly is not None and hotel.get('price_basis') == 'per_night' and nights > 0:
            total = nightly * nights
            basis = f"אומדן: {money(nightly, hotel.get('currency'))} × {nights} לילות"
        if total is not None and hotel.get('currency'):
            subtotals.append((total, hotel['currency']))
        lines.append(f"| {clean(hotel.get('name') or 'מלון')} | {money(nightly, hotel.get('currency'))} | {money(total, hotel.get('currency'))} | {basis if total is not None else 'בסיס המחיר דורש בירור'} |")
    if not proposal.hotel_options:
        lines.append('| טרם נמצאה אפשרות לינה | טרם תומחר | טרם תומחר | דרוש חיפוש נוסף |')
    lines += ['', 'המחירים מתייחסים לאפשרות הלינה שהחזיר החיפוש. יש לאשר מספר חדרים, התאמה לכל הנוסעים, מסים ותנאי ביטול. אין להכפיל מחיר במספר הנוסעים ללא בדיקת תפוסת החדר.', '', '## אפשרויות טיסה']
    for flight in proposal.flight_options[:3]:
        segments = flight.get('segments') or []
        airline = segments[0].get('airline') if segments else 'טיסה'
        lines.append(f"- **{clean(airline or 'טיסה')}:** {money(flight.get('amount'), flight.get('currency'))} — מחיר שהתקבל בחיפוש. יש לאשר שהוא כולל הלוך וחזור, את כל הנוסעים וכבודה.")
    if not proposal.flight_options:
        lines.append('לא נמצא מחיר טיסה מאומת. עלות הטיסות חסרה בסיכום.')
    lines += ['', '## סיכום התקציב', '| רכיב | סכום ומצב |', '| --- | --- |']
    for currency in sorted({currency for _, currency in subtotals}):
        minimum = min(total for total, code in subtotals if code == currency)
        lines.append(f'| לינה בלבד — החל מ־ | {money(minimum, currency)} לאחת החלופות המוצגות, בכפוף לאישור תפוסה |')
    if not subtotals:
        lines.append('| לינה | טרם תומחרה לשהות מלאה |')
    lines += ['| טיסות | נדרש אישור מחיר לכל הנוסעים; לא נכלל בסכום הלינה |' if proposal.flight_options else '| טיסות | חסר מחיר |',
              '| אוכל, תחבורה, אטרקציות וביטוח | טרם תומחרו |',
              '| עלות כוללת לטיול | עדיין לא ניתן לחשב — חסרים רכיבים מאומתים |', '',
              '**הסכום הידוע הוא ללינה בלבד, ולא מחיר החופשה כולה.** אין עדיין אפשרות לקבוע אם הטיול עומד בתקציב.', '']
    if proposal.daily_itinerary:
        lines.append('## המסלול היומי והמפה')
        for day in proposal.daily_itinerary:
            lines += [f"### יום {day.get('day_number', '')}: {day.get('title', '')}", str(day.get('summary') or '')]
            lines += [f'- [[{place}]]' for place in day.get('suggested_places', []) or []]
            lines.append('')
    notes = list(dict.fromkeys(MESSAGES.get(item, item) for item in proposal.assumptions + proposal.warnings))
    if notes:
        lines += ['## לפני שמזמינים'] + [f'- {item}' for item in notes] + ['']
    lines += ['---', 'זוהי תוכנית ראשונית לבדיקה. המחירים והזמינות עשויים להשתנות; הזמנה סופית תיעשה לאחר אישור סוכן נסיעות.']
    return '\n'.join(lines)
