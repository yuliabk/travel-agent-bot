"""Build minimized, hash-linked AuditBundle records for Contract v1."""

from __future__ import annotations

import hashlib
from typing import Optional

from src.contracts.travel_v1 import (
    ApprovalRecord,
    AuditBundle,
    AuditUsage,
    EvalResult,
    EvidencePack,
    ProposalDraft,
    TripRequest,
    canonical_hash,
)


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_audit_bundle(
    request: TripRequest,
    evidence_pack: EvidencePack,
    proposal: ProposalDraft,
    eval_result: EvalResult,
    *,
    system_version: str,
    agent_release_id: str,
    approval: Optional[ApprovalRecord] = None,
    final_output: Optional[str] = None,
    usage: Optional[AuditUsage] = None,
) -> AuditBundle:
    """Build a minimized audit record after validating cross-object linkage."""
    if evidence_pack.request_id != request.request_id:
        raise ValueError("evidence pack does not belong to request")
    if proposal.request_id != request.request_id:
        raise ValueError("proposal does not belong to request")
    if proposal.evidence_pack_id != evidence_pack.evidence_pack_id:
        raise ValueError("proposal does not belong to evidence pack")
    if eval_result.proposal_id != proposal.proposal_id or eval_result.proposal_version != proposal.version:
        raise ValueError("eval result does not belong to exact proposal version")
    if approval is not None and not approval.is_valid_for(proposal):
        raise ValueError("approval is not valid for exact proposal snapshot")

    return AuditBundle(
        request_id=request.request_id,
        proposal_id=proposal.proposal_id,
        proposal_version=proposal.version,
        request_hash=canonical_hash(request),
        evidence_pack_id=evidence_pack.evidence_pack_id,
        evidence_pack_hash=canonical_hash(evidence_pack),
        proposal_hash=canonical_hash(proposal),
        eval_id=eval_result.eval_id,
        approval_id=approval.approval_id if approval else None,
        final_output_hash=_text_hash(final_output) if final_output is not None else None,
        system_version=system_version,
        agent_release_id=agent_release_id,
        usage=usage or AuditUsage(),
    )
