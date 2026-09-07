"""Keyless rental-car discovery through the public OctoTrip MCP endpoint.

Results are observations, never booking-ready evidence. The remote server is
an optional discovery dependency and failures must leave the draft usable.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests

from src.contracts.travel_v1 import EvidenceRecord, EvidenceSourceStatus, EvidenceType


OCTOTRIP_MCP_URL = "https://mcp.octotrip.app/rental-cars/mcp"


def _json_from_sse(response: requests.Response) -> Dict[str, Any]:
    """Read either a regular JSON response or MCP's SSE data envelope."""
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            value = line.removeprefix("data:").strip()
            if value and value != "[DONE]":
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
    raise ValueError("OctoTrip returned no JSON event")


def _tool_payload(message: Dict[str, Any]) -> Dict[str, Any]:
    result = message.get("result") or {}
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("json"), dict):
            return item["json"]
        text = item.get("text")
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _decimal(value: Any) -> Optional[Decimal]:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def normalize_octotrip_results(data: Dict[str, Any]) -> List[EvidenceRecord]:
    """Normalize at most three cheapest category results."""
    candidates: List[tuple[Decimal, Dict[str, Any]]] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        price = _decimal(item.get("price"))
        currency = str(item.get("currency") or "").upper()
        booking_url = str(item.get("booking_url") or "")
        if price is None or len(currency) != 3 or not booking_url.startswith("https://"):
            continue
        candidates.append((price, item))
    candidates.sort(key=lambda entry: entry[0])

    records: List[EvidenceRecord] = []
    seen_categories = set()
    for price, item in candidates:
        category = str(item.get("category") or "unknown")[:100]
        if category.casefold() in seen_categories:
            continue
        seen_categories.add(category.casefold())
        booking_url = str(item["booking_url"])
        records.append(EvidenceRecord(
            type=EvidenceType.TRANSPORT,
            provider="octotrip/rental-cars",
            provider_reference=booking_url[:500],
            raw_reference=booking_url[:1000],
            amount=price,
            currency=str(item["currency"]).upper(),
            source_status=EvidenceSourceStatus.UNVERIFIED,
            normalized_data={
                "kind": "rental_car",
                "evidence_status": "observed",
                "booking_ready": False,
                "price_basis": "total_rental_observed",
                "name": str(item.get("name") or "Rental car")[:200],
                "vendor": str(item.get("vendor") or "")[:150],
                "category": category,
                "price_per_day": item.get("price_per_day"),
                "transmission": item.get("transmission"),
                "passengers": item.get("passengers"),
                "bags": item.get("bags"),
                "fuel_policy": item.get("fuel_policy"),
                "mileage": item.get("mileage"),
                "free_cancellation": item.get("free_cancellation"),
                "deposit": item.get("deposit"),
                "excess": item.get("excess"),
                "included_protections": item.get("included_protections") or [],
                "booking_url": booking_url,
                "affiliate_link": True,
                "pickup_location": data.get("pickup_location_resolved"),
                "dropoff_location": data.get("dropoff_location_resolved"),
                "rental_days": data.get("rental_days"),
            },
        ))
        if len(records) == 3:
            break
    return records


class OctoTripRentalCarsClientV1:
    def __init__(self, *, session: Any = requests, timeout: float = 9.0):
        self.session = session
        self.timeout = timeout

    def search_rental_cars(self, request: Any) -> List[EvidenceRecord]:
        location = request.arrival_airport or (
            request.stays[0].destination if request.stays else request.destination
        )
        payload = {
            "jsonrpc": "2.0",
            "id": f"rental-{request.request_id}",
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {
                    "location": location,
                    "pickup_date": request.departure_date.isoformat(),
                    "dropoff_date": request.return_date.isoformat(),
                    "currency": request.currency,
                },
            },
        }
        response = self.session.post(
            OCTOTRIP_MCP_URL,
            json=payload,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "User-Agent": "YB-Travel-Agent/1.0",
            },
            timeout=(3, self.timeout),
        )
        response.raise_for_status()
        message = _json_from_sse(response)
        if message.get("error"):
            raise RuntimeError("OctoTrip MCP request failed")
        data = _tool_payload(message)
        if data.get("error"):
            return []
        return normalize_octotrip_results(data)
