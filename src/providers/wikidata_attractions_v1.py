"""Keyless attraction lookup backed by Wikidata's public API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.contracts.travel_v1 import EvidenceRecord, EvidenceSourceStatus, EvidenceType
from src.providers.attraction_prices_v1 import name_key


WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


def _official_url(entity: Dict[str, Any]) -> Optional[str]:
    claims = entity.get("claims") or {}
    for claim in claims.get("P856") or []:
        try:
            value = claim["mainsnak"]["datavalue"]["value"]
        except (KeyError, TypeError):
            continue
        if isinstance(value, str) and value.startswith("https://"):
            return value[:1000]
    return None


class WikidataAttractionsClientV1:
    def __init__(self, *, session: Any = requests, timeout: float = 6.0):
        self.session = session
        self.timeout = timeout
        self.headers = {"User-Agent": "YB-Travel-Agent/1.0 (public-attraction-lookup)"}

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.get(
            WIKIDATA_API_URL,
            params={"format": "json", "origin": "*", **params},
            headers=self.headers,
            timeout=(3, self.timeout),
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _lookup(self, item: Tuple[str, str]) -> Optional[EvidenceRecord]:
        name, city = item
        search = self._get({
            "action": "wbsearchentities",
            "search": f"{name} {city}",
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": 5,
        })
        results = [result for result in search.get("search") or [] if isinstance(result, dict)]
        if not results:
            return None
        wanted = name_key(name)
        match = next(
            (result for result in results if name_key(result.get("label")) == wanted),
            results[0] if wanted and wanted in name_key(results[0].get("label")) else None,
        )
        if not match or not str(match.get("id") or "").startswith("Q"):
            return None
        entity_id = str(match["id"])
        entities = self._get({"action": "wbgetentities", "ids": entity_id, "props": "claims"})
        official_url = _official_url((entities.get("entities") or {}).get(entity_id) or {})
        wikidata_url = f"https://www.wikidata.org/wiki/{entity_id}"
        return EvidenceRecord(
            type=EvidenceType.PLACE,
            provider="wikidata/attractions",
            provider_reference=wikidata_url,
            raw_reference=official_url or wikidata_url,
            source_status=EvidenceSourceStatus.UNVERIFIED,
            normalized_data={
                "kind": "attraction",
                "name": name,
                "matched_name": str(match.get("label") or name)[:300],
                "city": city,
                "description": str(match.get("description") or "")[:500],
                "wikidata_id": entity_id,
                "source_url": wikidata_url,
                "official_url": official_url,
                "offers": [],
                "admission_price_status": "unknown",
                "date_and_age_price_verified": False,
            },
        )

    def search_attractions(self, request: Any, narrative: Any) -> List[EvidenceRecord]:
        unique: Dict[Tuple[str, str], Tuple[str, str]] = {}
        for day in narrative.days:
            city = (day.location or request.destination)[:200]
            for name in day.attractions:
                key = (name_key(name), name_key(city))
                if key[0]:
                    unique.setdefault(key, (name[:300], city))
        with ThreadPoolExecutor(max_workers=2) as pool:
            return [record for record in pool.map(self._lookup, list(unique.values())[:6]) if record]
