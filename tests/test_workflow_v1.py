from decimal import Decimal

from src.contracts.travel_v1 import ConsentStatus, EvidencePack, EvidenceRecord, EvidenceSourceStatus, EvidenceType
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion
from src.runtime.planner_v1 import PlannerDay, PlannerNarrative
from src.runtime.workflow_v1 import run_web_draft_workflow


def payload(**overrides):
    data = dict(
        name="Private Customer",
        email="private@example.com",
        phone="0501234567",
        destination="Rome",
        dateFrom="2026-10-10",
        dateTo="2026-10-15",
        adults=2,
        children=0,
        budget="בינוני",
        flightStops="nonstop",
        travelStyles=["תרבות"],
        specialRequests="Near public transport",
    )
    data.update(overrides)
    return AbacusWebFormPayload(**data)


def completion():
    return CanonicalCompletion(
        origin="Tel Aviv",
        budget_amount=Decimal("6000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
    )


class FakeSearch:
    def search_evidence(self, request, *, origin_iata, destination_iata):
        record = EvidenceRecord(
            type=EvidenceType.FLIGHT,
            provider="fixture",
            provider_reference="flight-ref",
            amount=Decimal("450"),
            currency="ILS",
            source_status=EvidenceSourceStatus.VERIFIED,
            normalized_data={"segments": [{"airline": "Example Air"}], "stops": 0, "price_basis": "total_offer"},
        )
        return EvidencePack(request_id=request.request_id, records=[record])


class FakePlanner:
    def generate_narrative(self, request, evidence_pack):
        return PlannerNarrative(
            summary="מסלול מוצע לרומא",
            days=[PlannerDay(day_number=1, title="המרכז ההיסטורי", summary="יום הליכה", suggested_places=["Colosseum"])],
        )


def test_missing_canonical_fields_stop_before_dependencies():
    class MustNotCall:
        def search_evidence(self, *args, **kwargs):
            raise AssertionError("search should not run")
        def generate_narrative(self, *args, **kwargs):
            raise AssertionError("planner should not run")

    result = run_web_draft_workflow(payload(), None, evidence_searcher=MustNotCall(), planner=MustNotCall())
    assert result.status == "NEEDS_INFORMATION"
    assert "origin" in result.missing_fields
    assert result.proposal is None


def test_no_live_dependencies_returns_partial_draft_not_failure():
    result = run_web_draft_workflow(payload(), completion())
    assert result.status == "PARTIAL_DRAFT"
    assert result.proposal is not None
    assert result.proposal.missing_information == ["itinerary_narrative"]
    assert "תוכנית ראשונית" in result.rendered_draft
    assert "לא נמצא מחיר טיסה מאומת" in result.rendered_draft


def test_complete_workflow_returns_traceable_ai_draft():
    result = run_web_draft_workflow(
        payload(),
        completion(),
        origin_iata="TLV",
        destination_iata="FCO",
        evidence_searcher=FakeSearch(),
        planner=FakePlanner(),
        model_version="fake-model",
    )
    assert result.status == "AI_DRAFT"
    assert result.proposal is not None
    assert result.proposal.flight_options[0]["amount"] == "450"
    assert result.proposal.flight_options[0]["provider_reference"] == "flight-ref"
    assert "Evidence:" not in result.rendered_draft
    assert "[[Colosseum]]" in result.rendered_draft
    assert "אישור סוכן נסיעות" in result.rendered_draft


def test_search_failure_degrades_to_partial_draft():
    class BrokenSearch:
        def search_evidence(self, *args, **kwargs):
            raise RuntimeError("provider down")

    result = run_web_draft_workflow(
        payload(),
        completion(),
        origin_iata="TLV",
        destination_iata="FCO",
        evidence_searcher=BrokenSearch(),
    )
    assert result.status == "PARTIAL_DRAFT"
    assert any("search failed" in warning.lower() for warning in result.proposal.warnings)


def test_renderer_does_not_echo_customer_pii():
    result = run_web_draft_workflow(payload(), completion(), planner=FakePlanner(), model_version="fake")
    text = result.rendered_draft
    assert "Private Customer" not in text
    assert "private@example.com" not in text
    assert "0501234567" not in text


def test_enabled_search_requires_airports_before_calling_providers():
    class MustNotCall:
        def search_evidence(self, *args, **kwargs):
            raise AssertionError("missing airports must stop search")
        def generate_narrative(self, *args, **kwargs):
            raise AssertionError("missing airports must stop planning")
    for origin, destination, missing in (
        (None, None, ["origin_iata", "destination_iata"]),
        ("TLV", None, ["destination_iata"]),
        (None, "FCO", ["origin_iata"]),
    ):
        result = run_web_draft_workflow(
            payload(), completion(), origin_iata=origin, destination_iata=destination,
            evidence_searcher=MustNotCall(), planner=MustNotCall(),
        )
        assert result.status == "NEEDS_INFORMATION"
        assert result.missing_fields == missing
        assert result.proposal is None


def test_planner_failure_logs_reason_without_raw_error(caplog):
    class BrokenPlanner:
        def generate_narrative(self, *args):
            raise RuntimeError("API key expired: SECRET_VALUE private@example.com")
    result = run_web_draft_workflow(payload(), completion(), planner=BrokenPlanner(), model_version="test-model")
    assert result.status == "PARTIAL_DRAFT"
    assert "reason=api_key_expired" in caplog.text
    assert "SECRET_VALUE" not in caplog.text
    assert "private@example.com" not in caplog.text
    assert "SECRET_VALUE" not in result.model_dump_json()
