"""Compatibility adapter for the current Abacus/Next.js booking form.

The adapter never invents canonical fields that the legacy form did not
collect. It returns an explicit gap report until missing values are supplied by
an approved UI change or a later clarification step.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from src.contracts.travel_v1 import (
    ChildTraveler,
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    FlightRoutingPreference,
    TravelerParty,
    TripPreferences,
    TripRequest,
)


class AbacusWebFormPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=40)
    destination: str = Field(..., min_length=2, max_length=200)
    dateFrom: Optional[str] = None
    dateTo: Optional[str] = None
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    budget: Optional[str] = Field(default=None, max_length=100)
    flightStops: str = "any"
    travelStyles: List[str] = Field(default_factory=list)
    specialRequests: Optional[str] = Field(default=None, max_length=4000)


class CanonicalCompletion(BaseModel):
    """Fields that the legacy form does not reliably provide."""

    origin: Optional[str] = Field(default=None, min_length=2, max_length=200)
    budget_amount: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    consent_status: Optional[ConsentStatus] = None
    child_ages: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_child_ages(self) -> "CanonicalCompletion":
        if any(age < 0 or age > 17 for age in self.child_ages):
            raise ValueError("child ages must be between 0 and 17")
        return self


class IntakeMigrationResult(BaseModel):
    canonical_request: Optional[TripRequest] = None
    missing_fields: List[str] = Field(default_factory=list)
    legacy_budget_label: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.canonical_request is not None and not self.missing_fields


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _routing(value: str) -> FlightRoutingPreference:
    normalized = (value or "any").strip().lower()
    if normalized in {"nonstop", "direct", "0"}:
        return FlightRoutingPreference.NONSTOP
    if normalized in {"onestop", "one_stop", "one-stop", "1"}:
        return FlightRoutingPreference.ONE_STOP
    return FlightRoutingPreference.ANY


def migrate_abacus_payload(
    payload: AbacusWebFormPayload,
    completion: Optional[CanonicalCompletion] = None,
    *,
    created_by_type: CreatedByType = CreatedByType.CUSTOMER,
) -> IntakeMigrationResult:
    """Map a legacy form submission to TripRequest v1 or return exact gaps."""

    completion = completion or CanonicalCompletion()
    departure = _parse_iso_date(payload.dateFrom)
    returned = _parse_iso_date(payload.dateTo)

    missing: List[str] = []
    if not departure:
        missing.append("departure_date")
    if not returned:
        missing.append("return_date")
    if not completion.origin:
        missing.append("origin")
    if completion.budget_amount is None:
        missing.append("budget")
    if not completion.currency:
        missing.append("currency")
    if completion.consent_status is None:
        missing.append("consent_status")
    if payload.children and len(completion.child_ages) != payload.children:
        missing.append("child_ages")

    if missing:
        return IntakeMigrationResult(
            missing_fields=missing,
            legacy_budget_label=payload.budget or None,
        )

    travelers = TravelerParty(
        adults=payload.adults,
        children=[ChildTraveler(age=age) for age in completion.child_ages],
    )
    preferences = TripPreferences(
        flight_routing=_routing(payload.flightStops),
        interests=payload.travelStyles,
        notes=payload.specialRequests,
    )

    request = TripRequest(
        created_by_type=created_by_type,
        customer=CustomerContact(name=payload.name, email=payload.email, phone=payload.phone),
        origin=completion.origin,
        destination=payload.destination,
        departure_date=departure,
        return_date=returned,
        travelers=travelers,
        budget=completion.budget_amount,
        currency=completion.currency,
        preferences=preferences,
        consent_status=completion.consent_status,
    )
    return IntakeMigrationResult(
        canonical_request=request,
        legacy_budget_label=payload.budget or None,
    )
