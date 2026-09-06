"""Normalize raw SerpApi search responses into Contract v1 evidence.

No network calls live here. Provider transport and credentials remain outside
this module so normalization can be evaluated deterministically with fixtures.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.contracts.travel_v1 import (
    EvidencePack,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
)

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_PRICE_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def normalize_iata_code(value: Optional[str]) -> Optional[str]:
    """Return a valid IATA code or None. Never substitute a different airport."""
    code = (value or "").strip().upper()
    return code if _IATA_RE.fullmatch(code) else None


def _decimal_price(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    match = _PRICE_RE.search(str(value).replace(",", ""))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _currency(data: Dict[str, Any]) -> Optional[str]:
    value = data.get("search_parameters", {}).get("currency") or data.get("currency")
    value = str(value or "").upper()
    return value if len(value) == 3 and value.isalpha() else None


def _search_id(data: Dict[str, Any]) -> Optional[str]:
    value = data.get("search_metadata", {}).get("id")
    return str(value) if value else None


def _source_status(price: Optional[Decimal], currency: Optional[str], ref: Optional[str]) -> EvidenceSourceStatus:
    if price is not None and currency and ref:
        return EvidenceSourceStatus.VERIFIED
    return EvidenceSourceStatus.UNVERIFIED


def _missing(*pairs: tuple[str, Any]) -> List[str]:
    return [name for name, value in pairs if value is None or value == ""]


def normalize_flights_response(data: Dict[str, Any]) -> List[EvidenceRecord]:
    currency = _currency(data)
    search_id = _search_id(data)
    records: List[EvidenceRecord] = []

    options: List[tuple[str, Dict[str, Any]]] = []
    for group in ("best_flights", "other_flights"):
        for item in data.get(group, []) or []:
            if isinstance(item, dict):
                options.append((group, item))

    for index, (group, option) in enumerate(options):
        legs = option.get("flights", []) or []
        price = _decimal_price(option.get("price"))
        provider_ref = f"serpapi:{search_id}:{group}:{index}" if search_id else None
        missing = _missing(
            ("price", price),
            ("currency", currency),
            ("provider_reference", provider_ref),
        )

        segments = []
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            segments.append(
                {
                    "airline": leg.get("airline"),
                    "flight_number": leg.get("flight_number"),
                    "departure_airport": leg.get("departure_airport"),
                    "arrival_airport": leg.get("arrival_airport"),
                    "duration": leg.get("duration"),
                }
            )

        records.append(
            EvidenceRecord(
                type=EvidenceType.FLIGHT,
                provider="serpapi/google_flights",
                provider_reference=provider_ref,
                currency=currency if price is not None else None,
                amount=price if currency else None,
                source_status=_source_status(price, currency, provider_ref),
                raw_reference=provider_ref,
                missing_fields=missing,
                normalized_data={
                    "group": group,
                    "segments": segments,
                    "stops": max(len(segments) - 1, 0) if segments else None,
                    "total_duration": option.get("total_duration"),
                    "price_basis": "total_offer",
                },
            )
        )
    return records


def normalize_hotels_response(data: Dict[str, Any]) -> List[EvidenceRecord]:
    currency = _currency(data)
    search_id = _search_id(data)
    records: List[EvidenceRecord] = []

    for index, hotel in enumerate(data.get("properties", []) or []):
        if not isinstance(hotel, dict):
            continue
        hotel_id = hotel.get("property_token") or hotel.get("place_id") or hotel.get("hotel_id")
        provider_ref = None
        if search_id:
            provider_ref = f"serpapi:{search_id}:hotel:{hotel_id or index}"
        nightly = hotel.get("rate_per_night") or {}
        price = _decimal_price(nightly.get("extracted_lowest", nightly.get("lowest")))
        total = hotel.get("total_rate") or {}
        stay_total = _decimal_price(total.get("extracted_lowest", total.get("lowest")))
        missing = _missing(
            ("price", price),
            ("currency", currency),
            ("provider_reference", provider_ref),
        )

        source_prices = []
        for item in hotel.get("prices", []) or []:
            if not isinstance(item, dict):
                continue
            source_prices.append(
                {
                    "source": item.get("source"),
                    "rate_per_night": (item.get("rate_per_night") or {}).get("lowest"),
                }
            )

        records.append(
            EvidenceRecord(
                type=EvidenceType.HOTEL,
                provider="serpapi/google_hotels",
                provider_reference=provider_ref,
                currency=currency if price is not None else None,
                amount=price if currency else None,
                source_status=_source_status(price, currency, provider_ref),
                raw_reference=provider_ref,
                missing_fields=missing,
                normalized_data={
                    "name": hotel.get("name"),
                    "property_token": hotel.get("property_token"),
                    "hotel_class": hotel.get("extracted_hotel_class") or hotel.get("hotel_class"),
                    "overall_rating": hotel.get("overall_rating"),
                    "price_basis": "per_night",
                    "stay_total": str(stay_total) if stay_total is not None and stay_total.is_finite() and stay_total >= 0 else None,
                    "source_prices": source_prices,
                },
            )
        )
    return records


def build_evidence_pack(
    request_id: str,
    *,
    flights_response: Optional[Dict[str, Any]] = None,
    hotels_response: Optional[Dict[str, Any]] = None,
) -> EvidencePack:
    records: List[EvidenceRecord] = []
    if flights_response is not None:
        records.extend(normalize_flights_response(flights_response))
    if hotels_response is not None:
        records.extend(normalize_hotels_response(hotels_response))
    return EvidencePack(request_id=request_id, records=records)
