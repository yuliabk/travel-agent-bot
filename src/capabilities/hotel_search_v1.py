"""Provider-neutral consumer for ``travel.hotel.search@1``.

The public shape contains only trip/hotel search fields. Provider selection,
credentials and scraping/MCP details stay behind the capability boundary.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Literal, Optional, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from src.contracts.travel_v1 import (
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    StaySegment,
    TripRequest,
)


class HotelSearchInputV1(BaseModel):
    destination: str = Field(..., min_length=2, max_length=200)
    check_in_date: date
    check_out_date: date
    adults: int = Field(..., ge=1, le=20)
    children_ages: List[int] = Field(default_factory=list, max_length=20)
    rooms: int = Field(default=1, ge=1, le=10)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    max_results: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_window(self) -> "HotelSearchInputV1":
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        if any(age < 0 or age > 17 for age in self.children_ages):
            raise ValueError("children ages must be between 0 and 17")
        return self


class HotelPriceV1(BaseModel):
    display_text: str = Field(..., min_length=1, max_length=100)
    amount: Optional[str] = Field(default=None, pattern=r"^[0-9]+(?:\.[0-9]+)?$")
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")
    basis: Literal["total_stay", "per_night", "unknown"] = "unknown"

    @model_validator(mode="after")
    def validate_pair(self) -> "HotelPriceV1":
        if (self.amount is None) != (self.currency is None):
            raise ValueError("price amount and currency must be supplied together")
        return self


class HotelOptionV1(BaseModel):
    option_id: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=300)
    room_text: Optional[str] = Field(default=None, max_length=500)
    location_text: Optional[str] = Field(default=None, max_length=500)
    star_rating: Optional[float] = Field(default=None, ge=0, le=5)
    guest_rating: Optional[float] = Field(default=None, ge=0, le=10)
    review_count: Optional[int] = Field(default=None, ge=0)
    free_cancellation: Optional[bool] = None
    price: HotelPriceV1
    booking_ready: bool = False
    evidence_status: Literal["observed", "provider-verified"] = "observed"
    source_ref: Optional[str] = Field(default=None, max_length=1000)


class HotelSearchOutputV1(BaseModel):
    status: Literal["complete", "partial", "unavailable"]
    search_id: str = Field(default_factory=lambda: f"hotel-{uuid4().hex}", min_length=1)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    options: List[HotelOptionV1] = Field(default_factory=list, max_length=20)
    limitations: List[str] = Field(default_factory=list)


class HotelSearchProviderV1(Protocol):
    def search(self, request: HotelSearchInputV1) -> HotelSearchOutputV1: ...


class HotelSearchConsumerV1:
    """Convert provider-neutral hotel results into Travel evidence records."""

    def __init__(self, provider: HotelSearchProviderV1) -> None:
        self.provider = provider

    def search_hotels(self, request: TripRequest) -> List[EvidenceRecord]:
        if request.return_date <= request.departure_date:
            return []
        stays = request.stays or [
            StaySegment(
                destination=request.destination,
                check_in=request.departure_date,
                check_out=request.return_date,
            )
        ]
        records: List[EvidenceRecord] = []
        children_ages = [child.age for child in request.travelers.children]

        for stay_index, stay in enumerate(stays):
            result = self.provider.search(
                HotelSearchInputV1(
                    destination=stay.destination,
                    check_in_date=stay.check_in,
                    check_out_date=stay.check_out,
                    adults=request.travelers.adults,
                    children_ages=children_ages,
                    rooms=1,
                    currency=request.currency,
                    max_results=5,
                )
            )
            for option in result.options:
                amount = option.price.amount
                currency = option.price.currency
                records.append(
                    EvidenceRecord(
                        type=EvidenceType.HOTEL,
                        provider="travel.hotel.search@1",
                        provider_reference=option.source_ref,
                        raw_reference=option.source_ref,
                        amount=amount,
                        currency=currency,
                        source_status=(
                            EvidenceSourceStatus.VERIFIED
                            if option.evidence_status == "provider-verified" and option.booking_ready
                            else EvidenceSourceStatus.UNVERIFIED
                        ),
                        normalized_data={
                            "kind": "hotel",
                            "evidence_status": option.evidence_status,
                            "booking_ready": option.booking_ready,
                            "name": option.name,
                            "room": option.room_text,
                            "location": option.location_text,
                            "hotel_class": option.star_rating,
                            "overall_rating": option.guest_rating,
                            "review_count": option.review_count,
                            "free_cancellation": option.free_cancellation,
                            "price_display": option.price.display_text,
                            "price_basis": option.price.basis,
                            "stay_total": amount if option.price.basis == "total_stay" else None,
                            "stay_index": stay_index,
                            "stay_destination": stay.destination,
                            "check_in": stay.check_in.isoformat(),
                            "check_out": stay.check_out.isoformat(),
                            "rooms_searched": 1,
                            "search_id": result.search_id,
                            "limitations": list(result.limitations),
                        },
                    )
                )
        return records
