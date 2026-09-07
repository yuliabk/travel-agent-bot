"""Read-only SerpApi transport for Contract v1 evidence search."""

from __future__ import annotations

import requests
from threading import Event
from src.providers.nearby_airports import nearby_airports
from concurrent.futures import ThreadPoolExecutor
from src.runtime.provider_diagnostics import log_provider_failure
from src.contracts.travel_v1 import EvidencePack, StaySegment, EvidenceRecord, EvidenceType, EvidenceSourceStatus
from src.providers.serpapi_evidence import normalize_flights_response, normalize_hotels_response

from src.contracts.travel_v1 import FlightRoutingPreference, TripRequest
from src.providers.serpapi_evidence import build_evidence_pack, normalize_iata_code

SERPAPI_URL = "https://serpapi.com/search"

_STOPS = {
    FlightRoutingPreference.ANY: 0,
    FlightRoutingPreference.NONSTOP: 1,
    FlightRoutingPreference.ONE_STOP: 2,
}


class SerpApiClientV1:
    def __init__(self, api_key: str, *, session=None, timeout: int = 15) -> None:
        if not api_key:
            raise ValueError("SerpApi key is required")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout
        self.rate_limited = Event()

    def _get(self, params: dict) -> dict:
        response = self.session.get(SERPAPI_URL, params=params, timeout=self.timeout)
        if response.status_code == 429:
            self.rate_limited.set()
            try:
                message = str(response.json().get("error", "")).lower()
            except Exception:
                message = ""
            reason = "quota_exceeded" if any(word in message for word in ("run out", "quota", "plan", "limit for", "credits")) else "rate_limited"
            raise requests.HTTPError(reason, response=response)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("SerpApi response must be a JSON object")
        safe_params = {k: v for k, v in params.items() if k != "api_key"}
        data.setdefault("search_parameters", safe_params)
        return data

    def search_attraction_prices(self, request, narrative):
        from src.providers.attraction_prices_v1 import search_attraction_prices
        return search_attraction_prices(self, request, narrative)

    def search_evidence(self, request: TripRequest, *, origin_iata: str, destination_iata: str, alternative_airports=None):
        origin = normalize_iata_code(origin_iata)
        destination = normalize_iata_code(destination_iata)
        if not origin or not destination:
            raise ValueError("valid explicit origin_iata and destination_iata are required")
        if origin == destination:
            raise ValueError("origin_iata and destination_iata must differ")

        children = len(request.travelers.children)
        flight_params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": request.departure_date.isoformat(),
            "return_date": request.return_date.isoformat(),
            "type": 1,
            "stops": _STOPS[request.preferences.flight_routing],
            "currency": request.currency,
            "hl": "en",
            "adults": request.travelers.adults,
            "children": children,
            "api_key": self.api_key,
        }
        hotel_params = {
            "engine": "google_hotels",
            "q": f"Hotels in {request.destination}",
            "check_in_date": request.departure_date.isoformat(),
            "check_out_date": request.return_date.isoformat(),
            "adults": request.travelers.adults,
            "children": children,
            "currency": request.currency,
            "hl": "en",
            "api_key": self.api_key,
        }

        stays = request.stays or [StaySegment(destination=request.destination, check_in=request.departure_date, check_out=request.return_date)] if request.return_date > request.departure_date else []
        notes = []

        def search(params):
            if self.rate_limited.is_set():
                return None
            try:
                data = self._get(params)
                if data.get("error"):
                    return None
                return data
            except Exception as exc:
                log_provider_failure("serpapi", exc, request_id=request.request_id)
                return None

        # Flight failures must not discard valid hotel results. Independent searches
        # share a bounded worker pool; later fallback searches keep the same dates.
        with ThreadPoolExecutor(max_workers=2) as pool:
            flight_future = pool.submit(search, flight_params)
            hotel_futures = [pool.submit(search, {**hotel_params, "q": f"Hotels in {stay.destination}", "check_in_date": stay.check_in.isoformat(), "check_out_date": stay.check_out.isoformat()}) for stay in stays]
            flight_data = flight_future.result()
            flights = normalize_flights_response(flight_data or {})
            for record in flights:
                record.normalized_data.update({"arrival_iata": destination, "alternative": False})
            records = list(flights)
            for index, (stay, future) in enumerate(zip(stays, hotel_futures)):
                data = future.result()
                hotels = normalize_hotels_response(data or {})
                if data is None:
                    notes.append(f"חיפוש הלינה ב־{stay.destination} לא הושלם. המחיר למקטע זה עדיין חסר.")
                for record in hotels:
                    record.normalized_data.update({"stay_index": index, "stay_destination": stay.destination, "check_in": stay.check_in.isoformat(), "check_out": stay.check_out.isoformat()})
                records.extend(hotels)

            relevant = [record for record in flights if record.is_verified_price and (record.currency != request.currency or record.amount <= request.budget)]
            if not relevant and not self.rate_limited.is_set():
                notes.append("לא התקבלה טיסה מתומחרת במסגרת התקציב לבקשה המקורית; נבדקו חלופות באותם תאריכים. אין בכך קביעה שאין טיסות זמינות.")
                # Explicit customer alternatives take precedence. Otherwise use a
                # worldwide geographic index, independent of destination spelling.
                nearby = nearby_airports(destination, exclude=(origin,)) if not alternative_airports else []
                candidates = alternative_airports or [item["code"] for item in nearby]
                candidates = list(dict.fromkeys(code for value in candidates if (code := normalize_iata_code(value)) and code not in (origin, destination)))[:3]
                distances = {item["code"]: item for item in nearby}
                def alternative_label(code):
                    label = f"חלופת נחיתה ב־{code}, כולל אפשרות לעצירות"
                    if code in distances:
                        item = distances[code]
                        label += f"; כ־{item['distance_km']} ק״מ בקו אווירי משדה הנחיתה המקורי"
                        if item['cross_border']:
                            label += "; במדינה אחרת — נדרשת בדיקת מעבר גבול"
                    return label + "; יש לבדוק זמן ועלות הגעה למקום הלינה"
                alternatives = []
                if request.preferences.flight_routing != FlightRoutingPreference.ANY:
                    alternatives.append(({**flight_params, "stops": 0}, "חלופה עם שינוי מגבלת העצירות"))
                alternatives += [({**flight_params, "arrival_id": code, "stops": 0}, alternative_label(code)) for code in candidates]
                pending = [(params, label, pool.submit(search, params)) for params, label in alternatives]
                for params, label, future in pending:
                    data = future.result()
                    found = normalize_flights_response(data or {})
                    notes.append(f"נבדקה {label}. " + ("נמצא מחיר להשוואה." if any(r.is_verified_price for r in found) else "לא התקבל מחיר מאומת."))
                    for record in found:
                        record.normalized_data.update({"arrival_iata": params["arrival_id"], "alternative": True, "alternative_note": label})
                    records.extend(found)
                if not alternatives:
                    notes.append("לא אותרו במאגר שדות חלופיים בטווח 300 ק״מ משדה הנחיתה שנבחר. אפשר להזין שדות חלופיים אחרים בבקשה.")
            cities = list(dict.fromkeys(stay.destination for stay in stays)) or [request.destination]
            if not self.rate_limited.is_set():
                restaurant_futures = [(city, pool.submit(search, {"engine": "google_maps", "type": "search", "q": f"restaurants in {city}", "hl": "en", "api_key": self.api_key})) for city in cities]
                for city, future in restaurant_futures:
                    data = future.result() or {}
                    for item in (data.get("local_results") or [])[:3]:
                        if not isinstance(item, dict) or not item.get("title"):
                            continue
                        records.append(EvidenceRecord(type=EvidenceType.PLACE, provider="serpapi/google_maps", source_status=EvidenceSourceStatus.UNVERIFIED,
                            provider_reference=str(item.get("place_id") or item.get("data_id") or data.get("search_metadata", {}).get("id") or "") or None,
                            normalized_data={"kind": "restaurant", "name": item["title"], "city": city, "address": item.get("address"), "price_label": item.get("price"), "rating": item.get("rating"), "website": item.get("website"), "place_id": item.get("place_id")}
                        ))
            if self.rate_limited.is_set():
                notes.append("ספק החיפוש חסם בקשות בגלל הגבלת קצב או מכסה (429). חיפוש הטיסות, החלופות או המסעדות לא הושלם; אין להסיק מכך שאין טיסות. נסו שוב מאוחר יותר; אם ההגבלה נמשכת נדרשת בדיקת מכסת החיפוש בחשבון.")
        return EvidencePack(request_id=request.request_id, records=records, search_notes=notes)