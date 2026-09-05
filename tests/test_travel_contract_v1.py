from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.contracts.travel_v1 import (
    ApprovalDecision,
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    EvalCheck,
    EvalCheckStatus,
    EvalOverallStatus,
    EvalResult,
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    FlightRoutingPreference,
    ProposalDraft,
    ProposalStatus,
    TripPreferences,
    TripRequest,
    TripRequestStatus,
    canonical_hash,
    create_approval,
    validate_proposal_transition,
    validate_trip_request_transition,
)


def make_request(**overrides):
    start = date.today() + timedelta(days=30)
    data = dict(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(name="Test Customer", email="test@example.com"),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=start,
        return_date=start + timedelta(days=4),
        budget=Decimal("5000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
        preferences=TripPreferences(flight_routing=FlightRoutingPreference.NONSTOP),
    )
    data.update(overrides)
    return TripRequest(**data)


def test_trip_request_requires_contact_channel():
    with pytest.raises(ValidationError):
        CustomerContact(name="No Contact")


def test_trip_request_rejects_invalid_dates():
    start = date.today() + timedelta(days=30)
    with pytest.raises(ValidationError):
        make_request(departure_date=start, return_date=start - timedelta(days=1))


def test_trip_request_schema_version_is_pinned():
    req = make_request()
    assert req.schema_version == "1.0.0"
    with pytest.raises(ValidationError):
        make_request(schema_version="2.0.0")


def test_verified_price_requires_traceable_fields():
    with pytest.raises(ValidationError):
        EvidenceRecord(
            type=EvidenceType.FLIGHT,
            provider="provider-x",
            amount=Decimal("100"),
            currency="USD",
            source_status=EvidenceSourceStatus.VERIFIED,
        )


def test_verified_price_is_identifiable():
    evidence = EvidenceRecord(
        type=EvidenceType.HOTEL,
        provider="provider-x",
        provider_reference="rate-123",
        amount=Decimal("300"),
        currency="USD",
        source_status=EvidenceSourceStatus.VERIFIED,
    )
    assert evidence.is_verified_price is True


def test_estimate_is_not_misrepresented_as_verified_price():
    evidence = EvidenceRecord(
        type=EvidenceType.PRICE,
        provider="planner",
        amount=Decimal("900"),
        currency="EUR",
        source_status=EvidenceSourceStatus.ESTIMATE,
    )
    assert evidence.is_verified_price is False


def test_partial_draft_requires_missing_information():
    with pytest.raises(ValidationError):
        ProposalDraft(
            request_id="req_1",
            model_version="model-v1",
            evidence_pack_id="ep_1",
            status=ProposalStatus.PARTIAL_DRAFT,
        )


def test_eval_cannot_claim_pass_when_check_fails():
    with pytest.raises(ValidationError):
        EvalResult(
            proposal_id="prop_0001",
            proposal_version=1,
            overall_status=EvalOverallStatus.PASS,
            checks=[EvalCheck(check_id="price-source", status=EvalCheckStatus.FAIL)],
        )


def test_approval_is_bound_to_exact_version_and_hash():
    proposal = ProposalDraft(
        proposal_id="prop_0001",
        request_id="req_1",
        version=3,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id="ep_1",
        summary="Original",
    )
    eval_result = EvalResult(
        proposal_id="prop_0001",
        proposal_version=3,
        overall_status=EvalOverallStatus.PASS,
        checks=[EvalCheck(check_id="traceability", status=EvalCheckStatus.PASS)],
    )
    approval = create_approval(proposal, eval_result, agent_id="agent-42")

    assert approval.decision == ApprovalDecision.APPROVED
    assert approval.is_valid_for(proposal) is True

    changed = proposal.model_copy(update={"version": 4, "summary": "Changed"})
    assert approval.is_valid_for(changed) is False


def test_failed_eval_blocks_approval():
    proposal = ProposalDraft(
        proposal_id="prop_0001",
        request_id="req_1",
        version=1,
        status=ProposalStatus.READY_FOR_REVIEW,
        model_version="model-v1",
        evidence_pack_id="ep_1",
    )
    eval_result = EvalResult(
        proposal_id="prop_0001",
        proposal_version=1,
        overall_status=EvalOverallStatus.FAIL,
        checks=[EvalCheck(check_id="traceability", status=EvalCheckStatus.FAIL)],
    )
    with pytest.raises(ValueError):
        create_approval(proposal, eval_result, agent_id="agent-42")


def test_canonical_hash_is_deterministic_and_changes_with_content():
    proposal = ProposalDraft(
        request_id="req_1",
        model_version="model-v1",
        evidence_pack_id="ep_1",
        summary="A",
    )
    assert canonical_hash(proposal) == canonical_hash(proposal)
    changed = proposal.model_copy(update={"summary": "B"})
    assert canonical_hash(proposal) != canonical_hash(changed)


def test_status_transition_guards():
    validate_trip_request_transition(TripRequestStatus.DRAFT, TripRequestStatus.SUBMITTED)
    with pytest.raises(ValueError):
        validate_trip_request_transition(TripRequestStatus.DRAFT, TripRequestStatus.READY_FOR_SEARCH)

    validate_proposal_transition(ProposalStatus.READY_FOR_REVIEW, ProposalStatus.APPROVED)
    with pytest.raises(ValueError):
        validate_proposal_transition(ProposalStatus.APPROVED, ProposalStatus.READY_FOR_REVIEW)
