from datetime import date, timedelta
from decimal import Decimal

from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvidencePack,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    ProposalStatus,
    TripRequest,
)
from src.runtime.planner_v1 import (
    PlannerDay,
    PlannerNarrative,
    build_planning_context,
    build_proposal_draft,
)


def request():
    start = date.today() + timedelta(days=30)
    return TripRequest(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(
            name="Private Customer",
            email="private@example.com",
            phone="0501234567",
        ),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=start,
        return_date=start + timedelta(days=4),
        budget=Decimal("5000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
    )


def verified_records(req):
    flight = EvidenceRecord(
        type=EvidenceType.FLIGHT,
        provider="fixture-flights",
        provider_reference="flight-1",
        amount=Decimal("500"),
        currency="USD",
        source_status=EvidenceSourceStatus.VERIFIED,
        normalized_data={
            "segments": [{"airline": "Example Air", "flight_number": "EA1"}],
            "stops": 0,
            "price_basis": "total_offer",
        },
    )
    hotel = EvidenceRecord(
        type=EvidenceType.HOTEL,
        provider="fixture-hotels",
        provider_reference="hotel-1",
        amount=Decimal("120"),
        currency="USD",
        source_status=EvidenceSourceStatus.VERIFIED,
        normalized_data={"name": "Hotel Roma", "price_basis": "per_night"},
    )
    return EvidencePack(request_id=req.request_id, records=[flight, hotel]), flight, hotel


def observed_flight(req):
    record = EvidenceRecord(
        type=EvidenceType.FLIGHT,
        provider="travel.flight.search",
        provider_reference="ffs-opt-1",
        amount=Decimal("199"),
        currency="USD",
        source_status=EvidenceSourceStatus.UNVERIFIED,
        normalized_data={
            "carrier": "Aegean Airlines",
            "departure": "2026-10-20 10:00 TLV",
            "arrival": "2026-10-20 12:10 ATH",
            "duration": "2h 10m",
            "stops": 0,
            "price_display": "USD 199",
            "booking_ready": False,
            "evidence_status": "observed",
            "price_basis": "observed_search_result",
        },
    )
    return EvidencePack(request_id=req.request_id, records=[record]), record


def test_planning_context_excludes_customer_pii():
    req = request()
    pack, _, _ = verified_records(req)
    context = build_planning_context(req, pack)
    serialized = str(context)
    assert "Private Customer" not in serialized
    assert "private@example.com" not in serialized
    assert "0501234567" not in serialized
    assert context["request"]["destination"] == "Rome"


def test_model_narrative_schema_contains_no_commercial_price_fields():
    fields = PlannerNarrative.model_fields
    assert "price" not in fields
    assert "amount" not in fields
    assert "currency" not in fields
    assert "hotel_options" not in fields
    assert "flight_options" not in fields


def test_verified_commercial_options_are_copied_from_evidence():
    req = request()
    pack, flight, hotel = verified_records(req)
    narrative = PlannerNarrative(
        summary="A four-day Rome draft.",
        days=[
            PlannerDay(
                day_number=1,
                title="Historic center",
                summary="Suggested walking day",
            )
        ],
    )
    proposal = build_proposal_draft(
        req,
        pack,
        narrative=narrative,
        model_version="model-v1",
    )
    assert proposal.status == ProposalStatus.AI_DRAFT
    assert proposal.flight_options[0]["amount"] == "500"
    assert proposal.flight_options[0]["price_status"] == "verified"
    assert proposal.flight_options[0]["provider_reference"] == "flight-1"
    assert proposal.hotel_options[0]["amount"] == "120"
    assert proposal.hotel_options[0]["provider_reference"] == "hotel-1"
    assert set(proposal.evidence_ids) == {flight.evidence_id, hotel.evidence_id}


def test_observed_flight_is_displayed_without_becoming_verified_or_booking_ready():
    req = request()
    pack, flight = observed_flight(req)
    proposal = build_proposal_draft(
        req,
        pack,
        narrative=PlannerNarrative(summary="Draft", days=[]),
        model_version="model-v1",
    )

    assert len(proposal.flight_options) == 1
    option = proposal.flight_options[0]
    assert option["carrier"] == "Aegean Airlines"
    assert option["price_status"] == "observed"
    assert option["observed_amount"] == "199"
    assert option["observed_currency"] == "USD"
    assert option["booking_ready"] is False
    assert "amount" not in option
    assert "currency" not in option
    assert flight.evidence_id in proposal.evidence_ids
    assert any("re-verified before booking" in warning for warning in proposal.warnings)

    context = build_planning_context(req, pack)
    exposed = context["evidence"][0]
    assert exposed["observed_amount"] == "199"
    assert "amount" not in exposed
    assert exposed["details"]["booking_ready"] is False


def test_unverified_hotel_price_is_not_exposed_as_commercial_option():
    req = request()
    unverified = EvidenceRecord(
        type=EvidenceType.HOTEL,
        provider="fixture",
        amount=Decimal("999"),
        currency="USD",
        source_status=EvidenceSourceStatus.UNVERIFIED,
        normalized_data={"name": "Unverified Hotel", "price_basis": "per_night"},
    )
    pack = EvidencePack(request_id=req.request_id, records=[unverified])
    narrative = PlannerNarrative(summary="Draft", days=[])
    proposal = build_proposal_draft(
        req,
        pack,
        narrative=narrative,
        model_version="model-v1",
    )
    assert proposal.hotel_options == []
    assert unverified.evidence_id not in proposal.evidence_ids
    assert any("verified hotel" in warning.lower() for warning in proposal.warnings)


def test_no_narrative_returns_partial_draft_instead_of_inventing_itinerary():
    req = request()
    pack, _, _ = verified_records(req)
    proposal = build_proposal_draft(
        req,
        pack,
        narrative=None,
        model_version="disabled",
    )
    assert proposal.status == ProposalStatus.PARTIAL_DRAFT
    assert proposal.daily_itinerary == []
    assert proposal.missing_information == ["itinerary_narrative"]


def test_aggregate_total_is_not_silently_computed_across_pricing_bases():
    req = request()
    pack, _, _ = verified_records(req)
    proposal = build_proposal_draft(
        req,
        pack,
        narrative=PlannerNarrative(summary="Draft", days=[]),
        model_version="model-v1",
    )
    assert proposal.estimated_total == []
    assert any("aggregate trip total" in warning.lower() for warning in proposal.warnings)
