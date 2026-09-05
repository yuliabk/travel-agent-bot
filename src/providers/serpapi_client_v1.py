"""Read-only SerpApi transport for Contract v1 evidence search."""

from __future__ import annotations

import requests

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

    def _get(self, params: dict) -> dict:
        response = self.session.get(SERPAPI_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("SerpApi response must be a JSON object")
        safe_params = {k: v for k, v in params.items() if k != "api_key"}
        data.setdefault("search_parameters", safe_params)
        return data

    def search_evidence(self, request: TripRequest, *, origin_iata: str, destination_iata: str):
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

        flights_response = self._get(flight_params)
        hotels_response = self._get(hotel_params)
        return build_evidence_pack(
            request.request_id,
            flights_response=flights_response,
            hotels_response=hotels_response,
        )
