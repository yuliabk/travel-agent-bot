from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvidencePack,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    FlightRoutingPreference,
    MoneyAmount,
    ProposalDraft,
    ProposalStatus,
    TripPreferences,
    TripRequest,
    create_approval,
)
from src.governance.audit_v1 import build_audit_bundle
from src.governance.evals_v1 import evaluate_proposal


def request():
    start = date.today() + timedelta(days=30)
    return TripRequest(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(name="Test", email="test@example.com"),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=start,
        return_date=start + timedelta(days=4),
        budget=Decimal("5000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
        preferences=TripPreferences(flight_routing=FlightRoutingPreference.NONSTOP),
    )


def verified_flight(req, stops=0):
    record = EvidenceRecord(
        type=EvidenceType.FLIGHT,
        provider="fixture",
        provider_reference="flight-1",
        amount=Decimal("500"),
        currency="USD",
        source_status=EvidenceSourceStatus.VERIFIED,
        normalized_data={"stops": stops},
    )
    return EvidencePack(request_id=req.request_id, records=[record]), record


def test_eval_passes_traceable_nonstop_proposal():
    req = request()
    pack, record = verified_flight(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
        estimated_total=[MoneyAmount(amount=Decimal("500"), currency="USD", is_estimate=False)],
    )
    result = evaluate_proposal(req, pack, proposal)
    assert result.can_approve is True
    assert result.overall_status.value == "PASS"


def test_eval_fails_when_proposal_references_missing_evidence():
    req = request()
    pack, _ = verified_flight(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=["ev_missing"],
    )
    result = evaluate_proposal(req, pack, proposal)
    assert result.can_approve is False
    assert result.overall_status.value == "FAIL"


def test_eval_fails_hard_nonstop_constraint():
    req = request()
    pack, record = verified_flight(req, stops=1)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    result = evaluate_proposal(req, pack, proposal)
    assert result.can_approve is False
    assert any(c.check_id == "hard-constraint-nonstop" and c.status.value == "FAIL" for c in result.checks)


def test_eval_fails_unverified_priced_evidence():
    req = request()
    record = EvidenceRecord(
        type=EvidenceType.HOTEL,
        provider="fixture",
        amount=Decimal("120"),
        currency="USD",
        source_status=EvidenceSourceStatus.UNVERIFIED,
        normalized_data={"price_basis": "per_night"},
    )
    pack = EvidencePack(request_id=req.request_id, records=[record])
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    result = evaluate_proposal(req, pack, proposal)
    assert result.can_approve is False


def test_audit_bundle_links_exact_approved_snapshot():
    req = request()
    pack, record = verified_flight(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    eval_result = evaluate_proposal(req, pack, proposal)
    approval = create_approval(proposal, eval_result, agent_id="agent-1")
    bundle = build_audit_bundle(
        req,
        pack,
        proposal,
        eval_result,
        approval=approval,
        final_output="Approved proposal",
        system_version="1.0.0",
        agent_release_id="travel-agent-test",
    )
    assert bundle.approval_id == approval.approval_id
    assert bundle.proposal_hash == approval.proposal_hash
    assert bundle.final_output_hash is not None


def test_audit_rejects_approval_for_modified_version():
    req = request()
    pack, record = verified_flight(req)
    proposal = ProposalDraft(
        request_id=req.request_id,
        version=1,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id=pack.evidence_pack_id,
        evidence_ids=[record.evidence_id],
    )
    eval_result = evaluate_proposal(req, pack, proposal)
    approval = create_approval(proposal, eval_result, agent_id="agent-1")
    changed = proposal.model_copy(update={"version": 2, "summary": "changed"})
    changed_eval = evaluate_proposal(req, pack, changed)
    with pytest.raises(ValueError):
        build_audit_bundle(
            req,
            pack,
            changed,
            changed_eval,
            approval=approval,
            system_version="1.0.0",
            agent_release_id="travel-agent-test",
        )
