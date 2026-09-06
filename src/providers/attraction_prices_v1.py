"""Read published admission options; never infer date/age-specific ticket prices.

Schema: https://serpapi.com/maps-place-results#api-examples-example-of-admission
Only exact name matches are accepted; ambiguous results stay unpriced.
"""
import re
import unicodedata
from math import isfinite
from concurrent.futures import ThreadPoolExecutor
from src.contracts.travel_v1 import EvidenceRecord, EvidenceType, EvidenceSourceStatus
from src.runtime.provider_diagnostics import log_provider_failure


def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold() if c.isalnum())


def search_attraction_prices(client, request, narrative):
    unique = {}
    for day in narrative.days:
        for name in day.attractions:
            city = day.location or request.destination
            key = (name_key(name), name_key(city))
            if key[0]:
                unique.setdefault(key, (name[:300], city[:200]))
    # At most 12 provider calls, with two concurrent workers. Unsearched places
    # remain explicitly missing in the renderer, rather than assumed free.
    def fetch(item):
        name, city = item
        if client.rate_limited.is_set():
            return None
        def get(params):
            if client.rate_limited.is_set():
                return {}
            return client._get({'engine': 'google_maps', 'hl': 'en', 'api_key': client.api_key, **params})
        try:
            data = get({'type': 'search', 'q': f'{name}, {city}'})
            place = data.get('place_results') or {}
            if not place:
                matches = [p for p in data.get('local_results', []) if isinstance(p, dict) and name_key(p.get('title', '')) == name_key(name)]
                if len(matches) != 1:
                    return None
                data_id = matches[0].get('data_id', '')
                if not re.fullmatch(r'0x[0-9a-f]+:0x[0-9a-f]+', data_id, re.I):
                    return None
                coords = matches[0].get('gps_coordinates') or {}
                lat, lon = coords.get('latitude'), coords.get('longitude')
                if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not isfinite(lat) or not isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                    return None
                data = get({'type': 'place', 'data': f'!4m5!3m4!1s{data_id}!8m2!3d{lat}!4d{lon}'})
                place = data.get('place_results') or {}
            if name_key(place.get('title', '')) != name_key(name):
                return None
            offers = []
            for seller in place.get('admission') or []:
                for option in seller.get('options') or []:
                    if isinstance(option.get('price'), str) and option['price'].strip():
                        offers.append({'ticket': str(option.get('title') or '')[:300], 'published_price': option['price'][:100], 'seller': str(seller.get('title') or '')[:150], 'official_site': option.get('official_site') is True})
            # Keep alternatives separate; guided experiences are deliberately not
            # substituted for admission and $ is never guessed to mean USD.
            offers.sort(key=lambda o: not o['official_site'])
            return EvidenceRecord(type=EvidenceType.PLACE, provider='serpapi/google_maps',
                source_status=EvidenceSourceStatus.UNVERIFIED,
                provider_reference=str(place.get('place_id') or place.get('data_id') or '') or None,
                normalized_data={'kind': 'attraction', 'name': name, 'city': city, 'offers': offers[:3], 'date_and_age_price_verified': False})
        except Exception as exc:
            log_provider_failure('attraction_search', exc, request_id=request.request_id)
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        return [record for record in pool.map(fetch, list(unique.values())[:6]) if record is not None]