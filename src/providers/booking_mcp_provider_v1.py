"""Temporary Booking.com hotel provider behind ``travel.hotel.search@1``.

This adapter talks to HasData's hosted Booking.com MCP server. HasData is a
third-party source, not an official Booking.com MCP service. Returned prices are
observations from public Booking.com pages and are never marked booking-ready.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from src.capabilities.hotel_search_v1 import (
    HotelOptionV1,
    HotelPriceV1,
    HotelSearchInputV1,
    HotelSearchOutputV1,
)


DEFAULT_BOOKING_MCP_URL = "https://mcp.hasdata.com/api/mcp?apis=booking"
SEARCH_TOOL = "hasdata_booking_search_getBookingSearchResults"
MCP_PROTOCOL_VERSION = "2025-06-18"


def _parse_rpc_response(response: requests.Response) -> Dict[str, Any]:
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        value = response.json()
        if isinstance(value, dict):
            return value
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        raw = line.removeprefix("data:").strip()
        if not raw or raw == "[DONE]":
            continue
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    raise ValueError("Booking MCP returned no JSON-RPC response")


def _safe_decimal(value: Any) -> Optional[str]:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number < 0:
        return None
    return format(number.normalize(), "f")


def _safe_booking_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "booking.com" or host.endswith(".booking.com")):
        return None
    return value[:1000]


def _number(value: Any, *, minimum: float, maximum: float) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if minimum <= number <= maximum else None


class BookingMcpProvider:
    """Read-only Booking.com search adapter using streamable HTTP MCP."""

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = DEFAULT_BOOKING_MCP_URL,
        session: Any = None,
        timeout: float = 15.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Booking MCP API key is required")
        self.api_key = api_key.strip()
        self.endpoint = endpoint.strip() or DEFAULT_BOOKING_MCP_URL
        self.session = session or requests.Session()
        self.timeout = timeout

    def _headers(self, session_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "User-Agent": "YB-Travel-Agent/1.0",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    def _post(
        self,
        payload: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        expect_response: bool = True,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        response = self.session.post(
            self.endpoint,
            json=payload,
            headers=self._headers(session_id),
            timeout=(3, self.timeout),
        )
        response.raise_for_status()
        next_session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id") or session_id
        if not expect_response or not response.content:
            return None, next_session_id
        message = _parse_rpc_response(response)
        if message.get("error"):
            raise RuntimeError("Booking MCP JSON-RPC request failed")
        return message, next_session_id

    def _initialize(self) -> Optional[str]:
        message, session_id = self._post({
            "jsonrpc": "2.0",
            "id": "hotel-init",
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "yb-travel-agent", "version": "1.0"},
            },
        })
        if not message or not isinstance(message.get("result"), dict):
            raise RuntimeError("Booking MCP initialize failed")
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            session_id=session_id,
            expect_response=False,
        )
        return session_id

    @staticmethod
    def _tool_json(message: Dict[str, Any]) -> Dict[str, Any]:
        result = message.get("result") or {}
        if result.get("isError"):
            raise RuntimeError("Booking MCP tool call returned an error")
        for item in result.get("content") or []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("json"), dict):
                return item["json"]
            text = item.get("text")
            if not isinstance(text, str):
                continue
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                nested = parsed.get("json")
                if isinstance(nested, dict):
                    return nested
                return parsed
        structured = result.get("structuredContent")
        return structured if isinstance(structured, dict) else {}

    def search(self, request: HotelSearchInputV1) -> HotelSearchOutputV1:
        session_id = self._initialize()
        children_ages = ",".join(str(age) for age in request.children_ages)
        arguments: Dict[str, Any] = {
            "keyword": request.destination,
            "checkInDate": request.check_in_date.isoformat(),
            "checkOutDate": request.check_out_date.isoformat(),
            "rooms": request.rooms,
            "adults": request.adults,
            "children": len(request.children_ages),
            "sort": "bestReviewedAndLowestPrice",
            "page": 1,
        }
        if children_ages:
            arguments["childrenAges"] = children_ages

        message, _ = self._post(
            {
                "jsonrpc": "2.0",
                "id": "hotel-search",
                "method": "tools/call",
                "params": {"name": SEARCH_TOOL, "arguments": arguments},
            },
            session_id=session_id,
        )
        if not message:
            raise RuntimeError("Booking MCP search returned no response")
        data = self._tool_json(message)
        raw_results = data.get("results") or []
        options = []
        for index, item in enumerate(raw_results):
            if not isinstance(item, dict) or not item.get("title"):
                continue
            price = item.get("price") if isinstance(item.get("price"), dict) else {}
            amount = _safe_decimal(price.get("pricePerStayParsed"))
            currency = str(price.get("currency") or "").upper()
            if amount is None or len(currency) != 3:
                amount = None
                currency = None
            source_ref = _safe_booking_url(item.get("url"))
            location = item.get("location") if isinstance(item.get("location"), dict) else {}
            reviews = item.get("reviews") if isinstance(item.get("reviews"), dict) else {}
            policies = item.get("policies") if isinstance(item.get("policies"), dict) else {}
            hotel_id = str(item.get("hotelId") or f"result-{index + 1}")
            display = f"{amount} {currency} total" if amount and currency else "price unavailable"
            options.append(
                HotelOptionV1(
                    option_id=hotel_id,
                    name=str(item["title"])[:300],
                    room_text=str(item.get("room"))[:500] if item.get("room") else None,
                    location_text=str(location.get("address") or location.get("city") or "")[:500] or None,
                    star_rating=_number(item.get("rating"), minimum=0, maximum=5),
                    guest_rating=_number(reviews.get("score"), minimum=0, maximum=10),
                    review_count=int(reviews["count"]) if isinstance(reviews.get("count"), int) and reviews["count"] >= 0 else None,
                    free_cancellation=policies.get("freeCancellation") if isinstance(policies.get("freeCancellation"), bool) else None,
                    price=HotelPriceV1(
                        display_text=display,
                        amount=amount,
                        currency=currency,
                        basis="total_stay" if amount and currency else "unknown",
                    ),
                    booking_ready=False,
                    evidence_status="observed",
                    source_ref=source_ref,
                )
            )
        priced = [option for option in options if option.price.amount is not None]
        unpriced = [option for option in options if option.price.amount is None]
        priced.sort(key=lambda option: Decimal(option.price.amount or "0"))
        selected = (priced + unpriced)[: request.max_results]
        request_metadata = data.get("requestMetadata") if isinstance(data.get("requestMetadata"), dict) else {}
        search_id = str(request_metadata.get("id") or data.get("searchId") or "booking-mcp-search")
        return HotelSearchOutputV1(
            status="complete",
            search_id=search_id,
            options=selected,
            limitations=[
                "Booking.com prices are observed from public pages and must be re-verified before booking",
                "search currently assumes one room for the full traveler party",
                "taxes, occupancy rules and cancellation terms may require property-level verification",
            ],
        )
