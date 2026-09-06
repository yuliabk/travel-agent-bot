"""Temporary deployed-runtime bridge for canonical ``travel.flight.search@1``.

This module exists only so the current Travel API deployment can exercise the
already-accepted provider-neutral flight capability before the Flight Provider
is deployed as a separate HTTP service. Travel business code still sees only
``CapabilityInvoker.invoke(capability_ref, payload)``.

The bridge is sandbox-only, returns observed/non-booking-ready evidence, and
must be replaced by the Core HTTP transport once ``flight-provider-sandbox``
has a separately deployed endpoint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from fast_flights import FlightQuery, Passengers, create_query, get_flights

from src.capabilities.flight_search_v1 import FLIGHT_SEARCH_REF, FlightSearchRequest


class SandboxFlightCapabilityInvokerV1:
    """In-process sandbox implementation of the canonical capability invoker."""

    def invoke(self, capability_ref: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if capability_ref != FLIGHT_SEARCH_REF:
            raise ValueError(f"unsupported capability: {capability_ref}")

        request = FlightSearchRequest.model_validate(dict(payload))
        data = request.model_dump(by_alias=True, mode="json")
        search_id = self._search_id(data)

        if data["adults"] + data["children"] > 9:
            return self._unavailable(
                search_id,
                "sandbox flight source supports at most 9 passengers per search",
            )

        legs = [
            FlightQuery(
                date=data["departureDate"],
                from_airport=data["originIata"],
                to_airport=data["destinationIata"],
                max_stops=data.get("maxStops"),
            )
        ]
        if data["tripType"] == "round-trip":
            legs.append(
                FlightQuery(
                    date=data["returnDate"],
                    from_airport=data["destinationIata"],
                    to_airport=data["originIata"],
                    max_stops=data.get("maxStops"),
                )
            )

        query = create_query(
            flights=legs,
            seat=data["cabin"],
            trip=data["tripType"],
            passengers=Passengers(adults=data["adults"], children=data["children"]),
            language="en-US",
            currency=data["currency"],
        )

        try:
            raw_result = get_flights(query)
            raw_options = list(self._extract_options(raw_result))
        except Exception:
            return self._unavailable(search_id, "sandbox flight source unavailable")

        carrier_names = self._carrier_name_map(raw_result)
        options: list[dict[str, Any]] = []
        for index, item in enumerate(raw_options[: data["maxResults"]], start=1):
            segments = list(getattr(item, "flights", []) or [])
            if not segments:
                continue

            first = segments[0]
            last = segments[-1]
            airline_codes = [str(code) for code in (getattr(item, "airlines", []) or [])]
            carriers = [carrier_names.get(code, code) for code in airline_codes]
            price_value = getattr(item, "price", None)
            amount = str(price_value) if isinstance(price_value, (int, float)) and price_value >= 0 else None

            options.append(
                {
                    "optionId": f"{search_id}-{index}",
                    "carrierText": ", ".join(carriers) if carriers else "Unknown carrier",
                    "departureText": self._format_endpoint(first, departure=True),
                    "arrivalText": self._format_endpoint(last, departure=False),
                    "durationText": self._elapsed_duration_text(first, last, segments),
                    "stops": max(0, len(segments) - 1),
                    "price": {
                        "displayText": f"{data['currency']} {amount}" if amount is not None else "price unavailable",
                        "amount": amount,
                        "currency": data["currency"] if amount is not None else None,
                    },
                    "isBest": bool(getattr(item, "rank", None) == 0),
                    "bookingReady": False,
                    "evidenceStatus": "observed",
                    "sourceRef": None,
                }
            )

        return {
            "status": "complete" if options else "unavailable",
            "searchId": search_id,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "options": options,
            "limitations": [
                "sandbox observed search; booking availability and fare are not guaranteed",
                "deployed Travel runtime is using the temporary in-process flight capability bridge",
                "provider output is normalized without exposing raw page content",
            ],
        }

    @staticmethod
    def _extract_options(raw_result: Any) -> Iterable[Any]:
        if isinstance(raw_result, (list, tuple)):
            return raw_result
        wrapped = getattr(raw_result, "flights", None)
        if wrapped is not None:
            return wrapped
        return raw_result or []

    @staticmethod
    def _carrier_name_map(raw_result: Any) -> dict[str, str]:
        metadata = getattr(raw_result, "metadata", None)
        airlines = getattr(metadata, "airlines", []) if metadata is not None else []
        return {
            str(getattr(item, "code", "")): str(getattr(item, "name", ""))
            for item in airlines
            if getattr(item, "code", None) and getattr(item, "name", None)
        }

    @classmethod
    def _format_endpoint(cls, segment: Any, *, departure: bool) -> str:
        point = getattr(segment, "departure" if departure else "arrival")
        airport = getattr(segment, "from_airport" if departure else "to_airport")
        date = getattr(point, "date", ())
        time = getattr(point, "time", ())
        if len(date) >= 3 and len(time) >= 2:
            stamp = (
                f"{int(date[0]):04d}-{int(date[1]):02d}-{int(date[2]):02d} "
                f"{int(time[0]):02d}:{int(time[1]):02d}"
            )
        else:
            stamp = "unknown time"
        code = str(getattr(airport, "code", "") or "").strip()
        name = str(getattr(airport, "name", "") or "").strip()
        return f"{stamp} {code or name or 'unknown airport'}"

    @classmethod
    def _elapsed_duration_text(cls, first: Any, last: Any, segments: list[Any]) -> str:
        try:
            start = cls._to_datetime(getattr(first, "departure"))
            end = cls._to_datetime(getattr(last, "arrival"))
            minutes = max(0, int((end - start).total_seconds() // 60))
        except Exception:
            minutes = sum(max(0, int(getattr(segment, "duration", 0) or 0)) for segment in segments)
        hours, remainder = divmod(minutes, 60)
        return f"{hours}h {remainder}m"

    @staticmethod
    def _to_datetime(value: Any) -> datetime:
        date = getattr(value, "date")
        time = getattr(value, "time")
        return datetime(int(date[0]), int(date[1]), int(date[2]), int(time[0]), int(time[1]))

    @staticmethod
    def _unavailable(search_id: str, reason: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "searchId": search_id,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "options": [],
            "limitations": [reason],
        }

    @staticmethod
    def _search_id(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "ffs-" + hashlib.sha256(canonical).hexdigest()[:16]
