from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.capabilities.research_lookup_v1 import (
    RESEARCH_LOOKUP_REF,
    ResearchLookupConsumerV1,
    ResearchLookupResponse,
)
from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvidencePack,
    EvidenceSourceStatus,
    EvidenceType,
    TravelerParty,
    TripPreferences,
    TripRequest,
)
from src.runtime.planner_v1 import build_planning_context


class FakeCapabilityInvoker:
    def __init__(self):
        self.calls = []

    def invoke(self, capability_ref, payload):
        self.calls.append((capability_ref, dict(payload)))
        return {
            "status": "complete",
            "answer": "Rome background research.",
            "findings": [
                {"statement": "The historic center is walkable.", "evidenceIds": ["e1"]}
            ],
            "evidence": [
                {
                    "id": "e1",
                    "sourceType": "web",
                    "sourceRef": "https://en.wikipedia.org/wiki/Rome",
                    "title": "Rome",
                    "summary": "Rome is the capital city of Italy.",
                    "retrievedAt": "2026-09-06T14:30:00Z",
                }
            ],
            "limitations": [],
        }


def trip_request():
    return TripRequest(
        request_id="req_research_consumer_1",
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(
            name="Private Customer",
            email="private@example.com",
            phone="0501234567",
        ),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=date(2026, 10, 10),
        return_date=date(2026, 10, 15),
        travelers=TravelerParty(adults=2),
        budget=Decimal("6000"),
        currency="ILS",
        preferences=TripPreferences(
            interests=["culture", "food"],
            preferred_areas=["historic center"],
            constraints=["near public transport"],
        ),
        consent_status=ConsentStatus.GRANTED,
    )


def test_request_is_pii_minimized_and_provider_neutral():
    invoker = FakeCapabilityInvoker()
    consumer = ResearchLookupConsumerV1(invoker)
    request = consumer.build_request(trip_request())
    dumped = request.model_dump(by_alias=True, mode="json")
    text = str(dumped)

    assert "Private Customer" not in text
    assert "private@example.com" not in text
    assert "0501234567" not in text
    assert "6000" not in text
    assert dumped["freshness"] == "any"
    assert "provider" not in dumped
    assert "model" not in dumped
    assert "tool" not in dumped


def test_consumer_invokes_only_research_lookup_and_maps_background_evidence():
    invoker = FakeCapabilityInvoker()
    consumer = ResearchLookupConsumerV1(invoker)
    records = consumer.search_background(trip_request())

    assert invoker.calls[0][0] == RESEARCH_LOOKUP_REF
    assert len(records) == 1
    record = records[0]
    assert record.type == EvidenceType.PLACE
    assert record.provider == "research.lookup"
    assert record.source_status == EvidenceSourceStatus.UNVERIFIED
    assert record.amount is None
    assert record.currency is None
    assert record.normalized_data["summary"] == "Rome is the capital city of Italy."


def test_research_output_rejects_provider_control_fields():
    with pytest.raises(ValidationError):
        ResearchLookupResponse.model_validate(
            {
                "status": "complete",
                "answer": "x",
                "findings": [],
                "evidence": [],
                "limitations": [],
                "provider": "caller-selected",
            }
        )


def test_planner_context_separates_background_from_commercial_evidence():
    invoker = FakeCapabilityInvoker()
    consumer = ResearchLookupConsumerV1(invoker)
    request = trip_request()
    pack = EvidencePack(request_id=request.request_id, records=consumer.search_background(request))

    context = build_planning_context(request, pack)
    assert context["evidence"] == []
    assert context["research_background"][0]["title"] == "Rome"
    assert context["research_background"][0]["source_ref"] == "https://en.wikipedia.org/wiki/Rome"
    assert context["policy"]["research_background_is_non_commercial_context"] is True
