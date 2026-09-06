from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import v1 as api_v1
from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvidencePack,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    ProposalDraft,
    ProposalStatus,
    TripRequest,
)


def client():
    app = FastAPI()
    app.include_router(api_v1.router)
    return TestClient(app)


def trip_request():
    start = date.today() + timedelta(days=20)
    return TripRequest(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(name="Dana", email="dana@example.com"),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=start,
        return_date=start + timedelta(days=3),
        budget=Decimal("5000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
    )


def evidence_for(req):
    record = EvidenceRecord(
        type=EvidenceType.FLIGHT,
        provider="fixture",
        provider_reference="flight-1",
        amount=Decimal("500"),
        currency="USD",
        source_status=EvidenceSourceStatus.VERIFIED,
        normalized_data={"stops": 0, "price_basis": "total_offer"},
    )
    return EvidencePack(request_id=req.request_id, records=[record]), record


def test_contract_endpoint_reports_no_external_side_effects(monkeypatch):
    monkeypatch.delenv("V1_LIVE_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("V1_CORE_FLIGHT_SANDBOX_ENABLED", raising=False)
    monkeypatch.delenv("V1_MODEL_PLANNER_ENABLED", raising=False)
    with client() as c:
        response = c.get("/v1/contract")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.0.0"
    assert response.json()["external_side_effects"] is False
    assert response.json()["live_search_enabled"] is False
    assert response.json()["governed_flight_search_enabled"] is True
    assert response.json()["model_planner_enabled"] is False


def test_contract_reports_feature_flags(monkeypatch):
    monkeypatch.setenv("V1_LIVE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("V1_CORE_FLIGHT_SANDBOX_ENABLED", "false")
    monkeypatch.setenv("V1_MODEL_PLANNER_ENABLED", "true")
    with client() as c:
        response = c.get("/v1/contract")
    assert response.status_code == 200
    assert response.json()["live_search_enabled"] is True
    assert response.json()["governed_flight_search_enabled"] is False
    assert response.json()["model_planner_enabled"] is True


def test_abacus_normalize_returns_explicit_gaps():
    payload = {
        "payload": {
            "name": "Dana",
            "email": "dana@example.com",
            "destination": "Rome",
            "dateFrom": "2026-10-10",
            "dateTo": "2026-10-15",
            "adults": 2,
            "children": 0,
            "budget": "mid",
        }
    }
    with client() as c:
        response = c.post("/v1/intake/abacus/normalize", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NEEDS_INFORMATION"
    assert set(body["missing_fields"]) == {"origin", "budget", "currency", "consent_status"}


def test_evidence_search_is_disabled_when_legacy_and_flight_are_disabled(monkeypatch):
    monkeypatch.delenv("V1_LIVE_SEARCH_ENABLED", raising=False)
    monkeypatch.setenv("V1_CORE_FLIGHT_SANDBOX_ENABLED", "false")
    req = trip_request()
    body = {
        "trip_request": req.model_dump(mode="json"),
        "origin_iata": "TLV",
        "destination_iata": "FCO",
    }
    with client() as c:
        response = c.post("/v1/evidence/search", json=body)
    assert response.status_code == 503


def test_evidence_search_returns_governed_flights_when_serp_disabled(monkeypatch):
    monkeypatch.delenv("V1_LIVE_SEARCH_ENABLED", raising=False)
    monkeypatch.setenv("V1_CORE_FLIGHT_SANDBOX_ENABLED", "true")

    class FakeFlightSearch:
        def search_flights(self, request, *, origin_iata, destination_iata):
            assert origin_iata == "TLV"
            assert destination_iata == "FCO"
            return [
                EvidenceRecord(
                    type=EvidenceType.FLIGHT,
                    provider="travel.flight.search",
                    provider_reference="observed-flight-1",
                    amount=Decimal("199"),
                    currency="USD",
                    source_status=EvidenceSourceStatus.UNVERIFIED,
                    normalized_data={
                        "booking_ready": False,
                        "evidence_status": "observed",
                        "price_basis": "observed_search_result",
                    },
                )
            ]

    monkeypatch.setattr(api_v1, "_flight_search", lambda: FakeFlightSearch())
    req = trip_request()
    body = {
        "trip_request": req.model_dump(mode="json"),
        "origin_iata": "TLV",
        "destination_iata": "FCO",
    }
    with client() as c:
        response = c.post("/v1/evidence/search", json=body)

    assert response.status_code == 200
    records = response.json()["evidence_pack"]["records"]
    assert len(records) == 1
    assert records[0]["type"] == "FLIGHT"
    assert records[0]["provider"] == "travel.flight.search"
    assert records[0]["source_status"] == "unverified"
    assert records[0]["normalized_data"]["booking_ready"] is False


def test_proposal_generation_returns_partial_evidence_draft_when_model_disabled(monkeypatch):
    monkeypatch.delenv("V1_MODEL_PLANNER_ENABLED", raising=False)
    req = trip_request()
    pack, record = evidence_for(req)
    body = {
        "trip_request": req.model_dump(mode="json"),
        "evidence_pack": pack.model_dump(mode="json"),
    }
    with client() as c:
        response = c.post("/v1/proposals/generate", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["planner_used"] is False
    assert result["proposal"]["status"] == "PARTIAL_DRAFT"
    assert result["proposal"]["missing_information"] == ["itinerary_narrative"]
    assert result["proposal"]["flight_options"][0]["amount"] == "500"
    assert result["proposal"]["evidence_ids"] == [record.evidence_id]


def test_approval_is_disabled_without_owner_token(monkeypatch):
    monkeypatch.delenv("OWNER_APPROVAL_TOKEN", raising=False)
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    body = {
        "trip_request": req.model_dump(mode="json"),
        "evidence_pack": pack.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
    }
    with client() as c:
        response = c.post(
            "/v1/proposals/approve",
            json=body,
            headers={"Authorization": "Bearer anything", "X-Agent-Id": "agent-1"},
        )
    assert response.status_code == 503


def test_approval_requires_valid_token(monkeypatch):
    monkeypatch.setenv("OWNER_APPROVAL_TOKEN", "secret-test-token")
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    body = {
        "trip_request": req.model_dump(mode="json"),
        "evidence_pack": pack.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
        "final_output": "Approved plan",
    }
    with client() as c:
        response = c.post(
            "/v1/proposals/approve",
            json=body,
            headers={"Authorization": "Bearer wrong", "X-Agent-Id": "agent-1"},
        )
    assert response.status_code == 403


def test_approval_returns_eval_approval_and_audit(monkeypatch):
    monkeypatch.setenv("OWNER_APPROVAL_TOKEN", "secret-test-token")
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    body = {
        "trip_request": req.model_dump(mode="json"),
        "evidence_pack": pack.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
        "final_output": "Approved plan",
    }
    with client() as c:
        response = c.post(
            "/v1/proposals/approve",
            json=body,
            headers={
                "Authorization": "Bearer secret-test-token",
                "X-Agent-Id": "agent-1",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["eval_result"]["overall_status"] == "PASS"
    assert body["approval"]["decision"] == "APPROVED"
    assert body["audit_bundle"]["approval_id"] == body["approval"]["approval_id"]
