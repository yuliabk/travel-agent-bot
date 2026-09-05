"""Deterministic Contract v1 proposal evaluations."""

from __future__ import annotations

from typing import List

from src.contracts.travel_v1 import (
    EvalCheck,
    EvalCheckStatus,
    EvalOverallStatus,
    EvalResult,
    EvidencePack,
    EvidenceType,
    FlightRoutingPreference,
    ProposalDraft,
    ProposalStatus,
    TripRequest,
)


def _check(check_id: str, ok: bool, pass_message: str, fail_message: str) -> EvalCheck:
    return EvalCheck(
        check_id=check_id,
        status=EvalCheckStatus.PASS if ok else EvalCheckStatus.FAIL,
        message=pass_message if ok else fail_message,
    )


def evaluate_proposal(request: TripRequest, evidence_pack: EvidencePack, proposal: ProposalDraft) -> EvalResult:
    """Evaluate traceability and hard invariants without model calls."""
    checks: List[EvalCheck] = []

    checks.append(
        _check(
            "request-link",
            proposal.request_id == request.request_id and evidence_pack.request_id == request.request_id,
            "proposal and evidence are linked to the request",
            "proposal/evidence request linkage mismatch",
        )
    )
    checks.append(
        _check(
            "evidence-pack-link",
            proposal.evidence_pack_id == evidence_pack.evidence_pack_id,
            "proposal references the evaluated evidence pack",
            "proposal evidence_pack_id does not match evaluated pack",
        )
    )

    by_id = {record.evidence_id: record for record in evidence_pack.records}
    missing_refs = [evidence_id for evidence_id in proposal.evidence_ids if evidence_id not in by_id]
    checks.append(
        _check(
            "evidence-references-exist",
            not missing_refs,
            "all proposal evidence references exist",
            f"missing evidence references: {missing_refs}",
        )
    )

    referenced = [by_id[evidence_id] for evidence_id in proposal.evidence_ids if evidence_id in by_id]
    priced = [record for record in referenced if record.amount is not None]
    invalid_priced = [record.evidence_id for record in priced if not record.is_verified_price]
    checks.append(
        _check(
            "priced-evidence-traceable",
            not invalid_priced,
            "all referenced prices are traceable",
            f"unverified priced evidence: {invalid_priced}",
        )
    )

    non_estimate_totals = [total for total in proposal.estimated_total if not total.is_estimate]
    unsupported_totals = []
    for total in non_estimate_totals:
        if not any(record.is_verified_price and record.currency == total.currency for record in referenced):
            unsupported_totals.append(total.currency)
    checks.append(
        _check(
            "non-estimate-total-supported",
            not unsupported_totals,
            "non-estimate totals have source-backed priced evidence",
            f"non-estimate totals lack source-backed evidence for currencies: {unsupported_totals}",
        )
    )

    if request.preferences.flight_routing == FlightRoutingPreference.NONSTOP:
        violating_flights = [
            record.evidence_id
            for record in referenced
            if record.type == EvidenceType.FLIGHT and record.normalized_data.get("stops") not in (None, 0)
        ]
        checks.append(
            _check(
                "hard-constraint-nonstop",
                not violating_flights,
                "referenced flights satisfy nonstop constraint",
                f"flight evidence violates nonstop constraint: {violating_flights}",
            )
        )
    elif request.preferences.flight_routing == FlightRoutingPreference.ONE_STOP:
        violating_flights = [
            record.evidence_id
            for record in referenced
            if record.type == EvidenceType.FLIGHT
            and isinstance(record.normalized_data.get("stops"), int)
            and record.normalized_data.get("stops") > 1
        ]
        checks.append(
            _check(
                "hard-constraint-one-stop",
                not violating_flights,
                "referenced flights satisfy one-stop constraint",
                f"flight evidence exceeds one-stop constraint: {violating_flights}",
            )
        )

    ready_with_gaps = proposal.status == ProposalStatus.READY_FOR_REVIEW and bool(proposal.missing_information)
    checks.append(
        _check(
            "review-readiness",
            not ready_with_gaps,
            "review status is consistent with information completeness",
            "READY_FOR_REVIEW proposal still declares missing information",
        )
    )

    statuses = {check.status for check in checks}
    if EvalCheckStatus.FAIL in statuses:
        overall = EvalOverallStatus.FAIL
    elif EvalCheckStatus.WARN in statuses:
        overall = EvalOverallStatus.PASS_WITH_WARNINGS
    else:
        overall = EvalOverallStatus.PASS

    return EvalResult(
        proposal_id=proposal.proposal_id,
        proposal_version=proposal.version,
        overall_status=overall,
        checks=checks,
    )
