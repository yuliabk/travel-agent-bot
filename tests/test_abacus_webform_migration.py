from decimal import Decimal

from src.contracts.travel_v1 import ConsentStatus, FlightRoutingPreference
from src.intake.abacus_webform_v1 import (
    AbacusWebFormPayload,
    CanonicalCompletion,
    migrate_abacus_payload,
)


def base_payload(**overrides):
    data = dict(
        name="Dana",
        email="dana@example.com",
        phone="0501234567",
        destination="Rome, Italy",
        dateFrom="2026-10-10",
        dateTo="2026-10-15",
        adults=2,
        children=0,
        budget="mid",
        flightStops="nonstop",
        carRental=False,
        travelStyles=["culture", "food"],
        specialRequests="Near public transport",
    )
    data.update(overrides)
    return AbacusWebFormPayload(**data)


def complete_fields(**overrides):
    data = dict(
        origin="Tel Aviv",
        budget_amount=Decimal("6000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
    )
    data.update(overrides)
    return CanonicalCompletion(**data)


def test_legacy_payload_fails_closed_when_canonical_fields_are_missing():
    result = migrate_abacus_payload(base_payload())
    assert result.canonical_request is None
    assert set(result.missing_fields) == {"origin", "budget", "currency", "consent_status"}
    assert result.legacy_budget_label == "mid"


def test_invalid_or_missing_dates_are_reported_not_invented():
    result = migrate_abacus_payload(
        base_payload(dateFrom="next week", dateTo=""),
        complete_fields(),
    )
    assert result.canonical_request is None
    assert "departure_date" in result.missing_fields
    assert "return_date" in result.missing_fields


def test_children_require_exact_ages_before_canonicalization():
    result = migrate_abacus_payload(
        base_payload(children=2),
        complete_fields(child_ages=[8]),
    )
    assert result.canonical_request is None
    assert result.missing_fields == ["child_ages"]


def test_complete_legacy_payload_maps_to_trip_request_v1():
    result = migrate_abacus_payload(base_payload(), complete_fields())
    assert result.is_complete is True
    req = result.canonical_request
    assert req is not None
    assert req.destination == "Rome, Italy"
    assert req.origin == "Tel Aviv"
    assert req.travelers.adults == 2
    assert req.preferences.flight_routing == FlightRoutingPreference.NONSTOP
    assert req.preferences.interests == ["culture", "food"]
    assert req.preferences.constraints == []
    assert req.preferences.notes == "Near public transport"
    assert req.schema_version == "1.0.0"


def test_rental_car_request_is_preserved_in_canonical_preferences():
    result = migrate_abacus_payload(base_payload(carRental=True), complete_fields())
    assert result.canonical_request is not None
    assert "rental_car_requested" in result.canonical_request.preferences.constraints


def test_one_stop_legacy_values_are_normalized():
    result = migrate_abacus_payload(base_payload(flightStops="oneStop"), complete_fields())
    assert result.canonical_request is not None
    assert result.canonical_request.preferences.flight_routing == FlightRoutingPreference.ONE_STOP
