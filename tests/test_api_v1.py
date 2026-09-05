from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1 import router
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
    app.include_router(router)
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
        normalized_data={"stops": 0},
    )
    return EvidencePack(request_id=req.request_id, records=[record]), record


def test_contract_endpoint_reports_no_external_side_effects(monkeypatch):
    monkeypatch.delenv("V1_LIVE_SEARCH_ENABLED", raising=False)
    with client() as c:
        response = c.get("/v1/contract")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.0.0"
    assert response.json()["external_side_effects"] is False
    assert response.json()["live_search_enabled"] is False


def test_contract_reports_live_search_feature_flag(monkeypatch):
    monkeypatch.setenv("V1_LIVE_SEARCH_ENABLED", "true")
    with client() as c:
        response = c.get("/v1/contract")
    assert response.status_code == 200
    assert response.json()["live_search_enabled"] is True


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


def test_live_evidence_search_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("V1_LIVE_SEARCH_ENABLED", raising=False)
    req = trip_request()
    body = {
        "trip_request": req.model_dump(mode="json"),
        "origin_iata": "TLV",
        "destination_iata": "FCO",
    }
    with client() as c:
        response = c.post("/v1/evidence/search", json=body)
    assert response.status_code == 503


def test_approval_is_disabled_without_owner_token(monkeypatch):
    monkeypatch.delenv("OWNER_APPROVAL_TOKEN", raising=False)
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(request_id=req.request_id, status=ProposalStatus.READY_FOR_REVIEW, model_version="model-v1", evidence_pack_id=pack.evidence_pack_id, evidence_ids=[record.evidence_id])
    body = {"trip_request": req.model_dump(mode="json"), "evidence_pack": pack.model_dump(mode="json"), "proposal": proposal.model_dump(mode="json")}
    with client() as c:
        response = c.post("/v1/proposals/approve", json=body, headers={"Authorization": "Bearer anything", "X-Agent-Id": "agent-1"})
    assert response.status_code == 503


def test_approval_requires_valid_token(monkeypatch):
    monkeypatch.setenv("OWNER_APPROVAL_TOKEN", "secret-test-token")
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(request_id=req.request_id, status=ProposalStatus.READY_FOR_REVIEW, model_version="model-v1", evidence_pack_id=pack.evidence_pack_id, evidence_ids=[record.evidence_id])
    body = {"trip_request": req.model_dump(mode="json"), "evidence_pack": pack.model_dump(mode="json"), "proposal": proposal.model_dump(mode="json"), "final_output": "Approved plan"}
    with client() as c:
        response = c.post("/v1/proposals/approve", json=body, headers={"Authorization": "Bearer wrong", "X-Agent-Id": "agent-1"})
    assert response.status_code == 403


def test_approval_returns_eval_approval_and_audit(monkeypatch):
    monkeypatch.setenv("OWNER_APPROVAL_TOKEN", "secret-test-token")
    req = trip_request()
    pack, record = evidence_for(req)
    proposal = ProposalDraft(request_id=req.request_id, status=ProposalStatus.READY_FOR_REVIEW, model_version="model-v1", evidence_pack_id=pack.evidence_pack_id, evidence_ids=[record.evidence_id])
    body = {"trip_request": req.model_dump(mode="json"), "evidence_pack": pack.model_dump(mode="json"), "proposal": proposal.model_dump(mode="json"), "final_output": "Approved plan"}
    with client() as c:
        response = c.post("/v1/proposals/approve", json=body, headers={"Authorization": "Bearer secret-test-token", "X-Agent-Id": "agent-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["eval_result"]["overall_status"] == "PASS"
    assert body["approval"]["decision"] == "APPROVED"
    assert body["audit_bundle"]["approval_id"] == body["approval"]["approval_id"]
