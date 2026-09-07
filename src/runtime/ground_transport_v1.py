"""Deterministic transport comparison scope; no invented fares or timetables."""


def ground_transport_plan(request, arrival_airports=()):
    stays = request.stays
    first = stays[0].destination if stays else request.destination
    last = stays[-1].destination if stays else request.destination
    airports = list(dict.fromkeys([request.arrival_airport] + list(arrival_airports)))
    legs = []
    for code in airports:
        if not code:
            continue
        conditional = code != request.arrival_airport
        legs.extend([
            {'origin': code, 'destination': first, 'date': request.departure_date.isoformat(), 'kind': 'airport_arrival', 'conditional': conditional},
            {'origin': last, 'destination': code, 'date': request.return_date.isoformat(), 'kind': 'airport_return', 'conditional': conditional},
        ])
    for previous, current in zip(stays, stays[1:]):
        if previous.destination.strip().casefold() != current.destination.strip().casefold():
            legs.append({'origin': previous.destination, 'destination': current.destination, 'date': current.check_in.isoformat(), 'kind': 'between_stays', 'conditional': False})
    return {
        'legs': legs,
        'local_transport_cities': list(dict.fromkeys(s.destination for s in stays)) or [request.destination],
        'modes_to_compare': ['public_transport', 'rental_car', 'mixed'],
        'traveler_count': request.travelers.adults + len(request.travelers.children),
        'prices_and_schedules_verified': False,
        'arrival_day_requires_flight_time_confirmation': True,
        'return_airport_requires_confirmation': True,
    }


def render_ground_transport(request, flight_options, rental_options=()):
    plan = ground_transport_plan(request, [f.get('arrival_iata') for f in flight_options])
    lines = ['## תחבורה ציבורית או רכב שכור',
             'משווים טיסה יחד עם ההגעה ללינה והחזרה לשדה. טיסה זולה יותר אינה בהכרח חלופה זולה או נוחה יותר לטיול כולו.',
             '| אפשרות | מה צריך לבדוק במסלול הזה | מה כלול בחישוב העלות |', '| --- | --- | --- |',
             f"| תחבורה ציבורית | רכבת ואוטובוס, מספר החלפות, הליכה עם מזוודות, שירות בשעת הנחיתה ובימי הטיול ונגישות | כרטיסים לכל {plan['traveler_count']} הנוסעים לפי גיל וזכאות, נסיעות מקומיות והגעה לתחנות; מחירים טרם אומתו |",
             '| רכב שכור | התאמה לנוסעים ולמזוודות, שעות איסוף והחזרה, רישיון וגיל נהג, חניה בלינה, תנאי הדרך ומעבר גבול | השכרה לכל תקופת השימוש, ביטוח, דלק, חניה, אגרות, כיסאות ילדים ותוספת החזרה במקום אחר; מחירים טרם אומתו |',
             '| שילוב | תחבורה ציבורית בערים ורכב רק לימים או למעברים שבהם הוא מתאים | כרטיסים רק למקטעי התחבורה הציבורית והשכרה רק לתקופת הרכב, כולל איסוף והחזרה |', '',
             '### מעברים להשוואה',
             'זמן הנסיעה, תדירות השירות והמחיר לכל מעבר עדיין דורשים בדיקה. עיר הלינה היא נקודת תכנון בלבד עד לבחירת כתובת מלון. יום ההגעה בפועל תלוי בשעת הנחיתה; שדה החזרה טרם אושר.',
             '| מועד תכנון | מעבר | מצב |', '| --- | --- | --- |']
    def clean(value):
        return str(value).replace('|', ' / ').replace('\n', ' ')
    for leg in plan['legs']:
        status = 'חלופת שדה להשוואה בלבד' if leg['conditional'] else 'לפי הבקשה'
        if leg['kind'] == 'airport_return':
            status += '; בהנחת חזרה מאותו שדה'
        display_date = '/'.join(reversed(leg['date'].split('-')))
        lines.append(f"| {display_date} | מ־{clean(leg['origin'])} אל {clean(leg['destination'])} | {status} |")
    if not plan['legs']:
        lines.append('| תאריכי הטיול | הגעה ללינה וחזרה לשדה | חסר שדה תעופה מאושר לבדיקת המעברים |')
    if rental_options:
        lines += ['', '### מחירי רכב שנצפו',
                  'המחירים התקבלו ממנוע השוואה חיצוני דרך קישורי שותפים. יש לאמת גיל נהג, ביטוח, פיקדון, השתתפות עצמית, מדיניות דלק ותנאי ביטול לפני הזמנה.',
                  '| רכב / ספק | קטגוריה | מחיר שנצפה לכל התקופה | פרטים |',
                  '| --- | --- | --- | --- |']
        for option in rental_options[:3]:
            currency = option.get('observed_currency') or ''
            amount = option.get('observed_amount')
            price = f"{amount} {currency}" if amount is not None and currency else 'לא התקבל מחיר'
            details = []
            if option.get('transmission'):
                details.append('אוטומטי' if option['transmission'] == 'automatic' else 'ידני' if option['transmission'] == 'manual' else 'גיר לא ידוע')
            if option.get('mileage'):
                details.append(str(option['mileage']))
            if option.get('free_cancellation') is True:
                details.append('ביטול חינם לפי הספק')
            if option.get('deposit') is not None:
                details.append(f"פיקדון מוצג: {option['deposit']} {currency}")
            name = clean(option.get('name') or 'רכב')
            vendor = clean(option.get('vendor') or 'ספק לא צוין')
            lines.append(f"| {name} / {vendor} | {clean(option.get('category') or 'לא צוין')} | {price} | {clean(', '.join(details) or 'יש לבדוק תנאים בקישור')} |")
    lines += ['', 'בנוסף יש לתכנן נסיעות יומיות ב־' + ', '.join(clean(c) for c in plan['local_transport_cities']) + '.',
              '**חישוב התקציב:** בוחרים תרחיש אחד - תחבורה ציבורית, רכב שכור או שילוב לפי מקטעים. אין לחבר את מחירי שתי החלופות במלואם, ואין לספור שוב דלק או כרטיסים שכבר נכללו. מחירי הרכב שנצפו אינם כוללים בהכרח את כל התוספות. אין מחיר כולל מאומת לתחבורה כרגע.', '']
    return lines
