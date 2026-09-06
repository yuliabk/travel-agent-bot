"""Provider-neutral consumer for Agent Factory `travel.flight.search@1`."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Literal, Mapping, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.contracts.travel_v1 import (
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    FlightRoutingPreference,
    TripRequest,
)


FLIGHT_SEARCH_REF = "travel.flight.search"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class FlightSearchRequest(StrictModel):
    origin_iata: str = Field(alias="originIata", pattern=r"^[A-Z]{3}$")
    destination_iata: str = Field(alias="destinationIata", pattern=r"^[A-Z]{3}$")
    departure_date: str = Field(alias="departureDate")
    return_date: Optional[str] = Field(alias="returnDate")
    trip_type: Literal["one-way", "round-trip"] = Field(alias="tripType")
    adults: int = Field(ge=1, le=9)
    children: int = Field(ge=0, le=8)
    cabin: Literal["economy", "premium-economy", "business", "first"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    max_stops: Optional[int] = Field(alias="maxStops", ge=0, le=2)
    max_results: int = Field(alias="maxResults", ge=1, le=20)


class FlightPrice(StrictModel):
    display_text: str = Field(alias="displayText", min_length=1)
    amount: Optional[str] = Field(default=None, pattern=r"^[0-9]+(?:\.[0-9]+)?$")
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def amount_currency_pair(self) -> "FlightPrice":
        if (self.amount is None) != (self.currency is None):
            raise ValueError("amount and currency must be supplied together")
        return self


class FlightOption(StrictModel):
    option_id: str = Field(alias="optionId", min_length=1)
    carrier_text: str = Field(alias="carrierText", min_length=1)
    departure_text: str = Field(alias="departureText", min_length=1)
    arrival_text: str = Field(alias="arrivalText", min_length=1)
    duration_text: str = Field(alias="durationText", min_length=1)
    stops: int = Field(ge=0)
    price: FlightPrice
    is_best: bool = Field(alias="isBest")
    booking_ready: bool = Field(alias="bookingReady")
    evidence_status: Literal["observed", "provider-verified"] = Field(alias="evidenceStatus")
    source_ref: Optional[str] = Field(alias="sourceRef", default=None)

    @model_validator(mode="after")
    def observed_evidence_cannot_claim_booking_ready(self) -> "FlightOption":
        if self.evidence_status == "observed" and self.booking_ready:
            raise ValueError("observed flight evidence cannot be booking-ready")
        return self


class FlightSearchResponse(StrictModel):
    status: Literal["complete", "partial", "unavailable"]
    search_id: str = Field(alias="searchId", min_length=1)
    observed_at: str = Field(alias="observedAt", min_length=1)
    options: List[FlightOption] = Field(default_factory=list, max_length=20)
    limitations: List[str] = Field(default_factory=list)


class CapabilityInvoker(Protocol):
    def invoke(self, capability_ref: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Invoke a capability selected by Core/runtime policy, never by Travel business code."""


class FlightSearchConsumerV1:
    """Build minimized flight-search requests and map capability output to Travel evidence."""

    def __init__(
        self,
        capability_invoker: CapabilityInvoker,
        *,
        cabin: Literal["economy", "premium-economy", "business", "first"] = "economy",
        max_results: int = 6,
    ) -> None:
        if not 1 <= max_results <= 20:
            raise ValueError("max_results must be between 1 and 20")
        self.capability_invoker = capability_invoker
        self.cabin = cabin
        self.max_results = max_results

    @staticmethod
    def _max_stops(request: TripRequest) -> Optional[int]:
        if request.preferences.flight_routing == FlightRoutingPreference.NONSTOP:
            return 0
        if request.preferences.flight_routing == FlightRoutingPreference.ONE_STOP:
            return 1
        return None

    def build_request(
        self,
        request: TripRequest,
        *,
        origin_iata: str,
        destination_iata: str,
    ) -> FlightSearchRequest:
        # Intentionally excludes customer identity, contact details, free-text notes,
        # interests, hotel preferences, and total trip budget.
        return FlightSearchRequest(
            originIata=origin_iata.strip().upper(),
            destinationIata=destination_iata.strip().upper(),
            departureDate=request.departure_date.isoformat(),
            returnDate=request.return_date.isoformat(),
            tripType="round-trip",
            adults=request.travelers.adults,
            children=len(request.travelers.children),
            cabin=self.cabin,
            currency=request.currency,
            maxStops=self._max_stops(request),
            maxResults=self.max_results,
        )

    def lookup(
        self,
        request: TripRequest,
        *,
        origin_iata: str,
        destination_iata: str,
    ) -> FlightSearchResponse:
        capability_request = self.build_request(
            request,
            origin_iata=origin_iata,
            destination_iata=destination_iata,
        )
        raw = self.capability_invoker.invoke(
            FLIGHT_SEARCH_REF,
            capability_request.model_dump(by_alias=True, mode="json"),
        )
        return FlightSearchResponse.model_validate(dict(raw))

    def search_flights(
        self,
        request: TripRequest,
        *,
        origin_iata: str,
        destination_iata: str,
    ) -> List[EvidenceRecord]:
        result = self.lookup(
            request,
            origin_iata=origin_iata,
            destination_iata=destination_iata,
        )
        records: List[EvidenceRecord] = []

        for option in result.options:
            amount = Decimal(option.price.amount) if option.price.amount is not None else None
            currency = option.price.currency if amount is not None else None
            verified = (
                option.evidence_status == "provider-verified"
                and option.booking_ready
                and amount is not None
                and currency is not None
                and bool(option.source_ref)
            )
            source_status = (
                EvidenceSourceStatus.VERIFIED if verified else EvidenceSourceStatus.UNVERIFIED
            )
            provider_reference = option.source_ref or option.option_id
            missing_fields: List[str] = []
            if amount is None:
                missing_fields.extend(["price.amount", "price.currency"])
            if option.source_ref is None:
                missing_fields.append("sourceRef")

            records.append(
                EvidenceRecord(
                    type=EvidenceType.FLIGHT,
                    provider=FLIGHT_SEARCH_REF,
                    provider_reference=provider_reference[:500],
                    currency=currency,
                    amount=amount,
                    source_status=source_status,
                    raw_reference=option.source_ref[:1000] if option.source_ref else None,
                    missing_fields=[] if verified else missing_fields,
                    normalized_data={
                        "search_id": result.search_id,
                        "observed_at": result.observed_at,
                        "option_id": option.option_id,
                        "carrier": option.carrier_text,
                        "departure": option.departure_text,
                        "arrival": option.arrival_text,
                        "duration": option.duration_text,
                        "stops": option.stops,
                        "price_display": option.price.display_text,
                        "is_best": option.is_best,
                        "booking_ready": option.booking_ready,
                        "evidence_status": option.evidence_status,
                        "limitations": list(result.limitations),
                        "price_basis": "observed_search_result",
                    },
                )
            )

        return records
