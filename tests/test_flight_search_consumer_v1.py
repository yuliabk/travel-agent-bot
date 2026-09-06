import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.capabilities.flight_search_v1 import (
    FLIGHT_SEARCH_REF,
    FlightOption,
    FlightSearchConsumerV1,
)
from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvidencePack,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    TravelerParty,
    TripPreferences,
    TripRequest,
)
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion
from src.runtime.workflow_v1 import run_web_draft_workflow


ROOT = Path(__file__).resolve().parents[1]


class FakeCapabilityInvoker:
    def __init__(self):
        self.calls = []

    def invoke(self, capability_ref, payload):
        self.calls.append((capability_ref, dict(payload)))
        return {
            "status": "complete",
            "searchId": "flight-search-1",
            "observedAt": "2026-09-06T16:00:00Z",
            "options": [
                {
                    "optionId": "observed-1",
                    "carrierText": "Example Air",
                    "departureText": "2026-10-10 10:00 TLV",
                    "arrivalText": "2026-10-10 12:30 ATH",
                    "durationText": "2h 30m",
                    "stops": 0,
                    "price": {
                        "displayText": "USD 420",
                        "amount": "420",
                        "currency": "USD",
                    },
                    "isBest": False,
                    "bookingReady": False,
                    "evidenceStatus": "observed",
                    "sourceRef": None,
                }
            ],
            "limitations": ["sandbox observed search; booking availability is not guaranteed"],
        }


def trip_request():
    return TripRequest(
        request_id="req_flight_consumer_1",
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(
            name="Private Customer",
            email="private@example.com",
            phone="0501234567",
        ),
        origin="Tel Aviv",
        destination="Athens",
        departure_date=date(2026, 10, 10),
        return_date=date(2026, 10, 15),
        travelers=TravelerParty(adults=2),
        budget=Decimal("6000"),
        currency="USD",
        preferences=TripPreferences(flight_routing="nonstop"),
        consent_status=ConsentStatus.GRANTED,
    )


def web_payload():
    return AbacusWebFormPayload(
        name="Private Customer",
        email="private@example.com",
        phone="0501234567",
        destination="Athens",
        dateFrom="2026-10-10",
        dateTo="2026-10-15",
        adults=2,
        children=0,
        budget="בינוני",
        flightStops="nonstop",
        travelStyles=["food"],
        specialRequests="Window seat",
    )


def web_completion():
    return CanonicalCompletion(
        origin="Tel Aviv",
        budget_amount=Decimal("6000"),
        currency="USD",
        consent_status=ConsentStatus.GRANTED,
    )


def test_request_is_pii_minimized_and_provider_neutral():
    invoker = FakeCapabilityInvoker()
    request = FlightSearchConsumerV1(invoker).build_request(
        trip_request(),
        origin_iata="TLV",
        destination_iata="ATH",
    )
    dumped = request.model_dump(by_alias=True, mode="json")
    text = json.dumps(dumped, sort_keys=True)

    assert "Private Customer" not in text
    assert "private@example.com" not in text
    assert "0501234567" not in text
    assert "6000" not in text
    assert dumped["originIata"] == "TLV"
    assert dumped["destinationIata"] == "ATH"
    assert dumped["tripType"] == "round-trip"
    assert dumped["maxStops"] == 0
    assert dumped["cabin"] == "economy"
    for forbidden in ("provider", "adapter", "scraper", "google", "apiKey", "implementationId"):
        assert forbidden not in dumped


def test_consumer_invokes_only_flight_capability_and_maps_observed_evidence():
    invoker = FakeCapabilityInvoker()
    records = FlightSearchConsumerV1(invoker).search_flights(
        trip_request(),
        origin_iata="TLV",
        destination_iata="ATH",
    )

    assert invoker.calls[0][0] == FLIGHT_SEARCH_REF
    assert len(records) == 1
    record = records[0]
    assert record.type == EvidenceType.FLIGHT
    assert record.provider == FLIGHT_SEARCH_REF
    assert record.source_status == EvidenceSourceStatus.UNVERIFIED
    assert record.amount == Decimal("420")
    assert record.currency == "USD"
    assert record.is_verified_price is False
    assert record.normalized_data["booking_ready"] is False
    assert record.normalized_data["evidence_status"] == "observed"
    assert record.raw_reference is None


def test_observed_output_cannot_claim_booking_ready():
    with pytest.raises(ValidationError):
        FlightOption.model_validate(
            {
                "optionId": "bad-1",
                "carrierText": "Example Air",
                "departureText": "10:00",
                "arrivalText": "12:00",
                "durationText": "2h",
                "stops": 0,
                "price": {"displayText": "USD 100", "amount": "100", "currency": "USD"},
                "isBest": False,
                "bookingReady": True,
                "evidenceStatus": "observed",
                "sourceRef": None,
            }
        )


def test_current_sandbox_manifest_requests_only_public_capability_authority():
    manifest = json.loads(
        (ROOT / "agent-factory/sandbox-agent-manifest.json").read_text(encoding="utf-8")
    )
    requested = set(manifest["spec"]["permissions"]["requested"])
    required_refs = {
        item["ref"] for item in manifest["spec"]["capabilities"]["requires"]
    }

    assert requested == {"research.lookup", "travel.flight.search"}
    assert required_refs == {"research.lookup", "travel.flight.search"}
    assert "web.search" not in requested
    assert "serpapi" not in json.dumps(manifest).lower()
    assert "google" not in json.dumps(manifest).lower()


def test_workflow_prefers_governed_flight_records_and_preserves_legacy_hotels():
    class LegacyCommercial:
        def search_evidence(self, request, *, origin_iata, destination_iata):
            return EvidencePack(
                request_id=request.request_id,
                records=[
                    EvidenceRecord(
                        type=EvidenceType.FLIGHT,
                        provider="legacy-flight",
                        source_status=EvidenceSourceStatus.UNVERIFIED,
                        normalized_data={"legacy": True},
                    ),
                    EvidenceRecord(
                        type=EvidenceType.HOTEL,
                        provider="legacy-hotel",
                        source_status=EvidenceSourceStatus.UNVERIFIED,
                        normalized_data={"name": "Hotel Example"},
                    ),
                ],
            )

    flight_consumer = FlightSearchConsumerV1(FakeCapabilityInvoker())
    result = run_web_draft_workflow(
        web_payload(),
        web_completion(),
        origin_iata="TLV",
        destination_iata="ATH",
        evidence_searcher=LegacyCommercial(),
        flight_search=flight_consumer,
    )

    assert result.evidence_pack is not None
    flight_records = [r for r in result.evidence_pack.records if r.type == EvidenceType.FLIGHT]
    hotel_records = [r for r in result.evidence_pack.records if r.type == EvidenceType.HOTEL]
    assert len(flight_records) == 1
    assert flight_records[0].provider == FLIGHT_SEARCH_REF
    assert len(hotel_records) == 1
    assert hotel_records[0].provider == "legacy-hotel"


def test_flight_capability_failure_degrades_without_stopping_draft():
    class BrokenFlightSearch:
        def search_flights(self, request, *, origin_iata, destination_iata):
            raise RuntimeError("capability unavailable")

    result = run_web_draft_workflow(
        web_payload(),
        web_completion(),
        origin_iata="TLV",
        destination_iata="ATH",
        flight_search=BrokenFlightSearch(),
    )

    assert result.status == "PARTIAL_DRAFT"
    assert any("governed flight search capability failed" in warning.lower() for warning in result.proposal.warnings)


def test_no_live_commercial_warning_when_governed_flight_search_executes():
    result = run_web_draft_workflow(
        web_payload(),
        web_completion(),
        origin_iata="TLV",
        destination_iata="ATH",
        flight_search=FlightSearchConsumerV1(FakeCapabilityInvoker()),
    )

    warnings = [warning.lower() for warning in result.proposal.warnings]
    assert not any(warning == "live commercial evidence search was not executed.".lower() for warning in warnings)
    assert any("hotel commercial evidence search was not executed" in warning for warning in warnings)
