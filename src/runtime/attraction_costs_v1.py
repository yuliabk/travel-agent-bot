"""Admission pricing belongs to each planned visit, not a sum of ticket offers."""
from datetime import timedelta
from src.providers.attraction_prices_v1 import name_key


def render_attraction_costs(request, proposal):
    def clean(value):
        return str(value or '').replace('|', ' / ').replace('\n', ' ')
    indexed = {(name_key(r.get('name')), name_key(r.get('city'))): r for r in proposal.attraction_options}
    lines = ['## עלויות אטרקציות לפי ימים',
             'מחיר שפורסם הוא נקודת פתיחה לבדיקה, ולא הצעת מחיר מאומתת לתאריך הביקור. סוג הכרטיס, גיל הנוסעים והנחות עשויים לשנות את המחיר. בוחרים כרטיס אחד לכל ביקור; אין לחבר חלופות כרטיסים.', '']
    count = 0
    for day in proposal.daily_itinerary:
        names = list(dict.fromkeys(day.get('attractions') or []))
        if not names:
            continue
        count += len(names)
        number = day.get('day_number', 1)
        visit = request.departure_date + timedelta(days=number - 1)
        city = day.get('location') or request.destination
        lines += [f'### אטרקציות ביום {number} — {visit:%d/%m/%Y}',
                  '| אטרקציה | מחירי כניסה שפורסמו | מחיר למבוגר / לילד | עלות לכל המשפחה |', '| --- | --- | --- | --- |']
        for name in names:
            record = indexed.get((name_key(name), name_key(city)), {})
            offers = record.get('offers') or []
            published = '; '.join(f"{clean(o.get('ticket') or 'כרטיס כניסה')}: {clean(o.get('published_price'))} ({clean(o.get('seller'))})" for o in offers) or 'לא התקבל מחיר — אין להסיק שהכניסה חינם'
            if offers:
                published += ' · נצפה: ' + clean(record.get('searched_at', '')[:10]) + ' · המטבע כפי שפורסם'
            lines.append(f'| [[{clean(name)}, {clean(city)}]] | {published} | טרם אומתו לתאריך ולגילים | לא ניתן לחשב עדיין |')
        lines += ['', '**סך אטרקציות ליום:** טרם ניתן לחשב מחיר משפחתי מאומת.', '']
    if not count:
        lines += ['טרם התקבלה רשימת אטרקציות יומית לתמחור. עלות האטרקציות עדיין חסרה בתקציב.', '']
    else:
        lines += ['החיפוש הראשוני מוגבל לעד שש אטרקציות שונות; מקומות נוספים או שלא זוהו בוודאות מסומנים ללא מחיר.',
                  '**סך אטרקציות לכל הטיול:** חסר תמחור משפחתי מאומת. אין להכפיל מחיר כללי במספר הנוסעים, לחבר מטבעות שונים או להחשיב מחיר חסר כאפס.', '']
    return lines