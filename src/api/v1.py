"""Contract v1 API surface.

These endpoints are deliberately side-effect free: no provider calls, booking,
payment, email, WhatsApp or database mutation. Approval is fail-closed unless
an owner approval token is configured in the runtime environment.
"""

from __future__ import annotations

import hmac
import os
from typing import List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.contracts.travel_v1 import (
    ApprovalRecord,
    AuditBundle,
    EvalResult,
    EvidencePack,
    ProposalDraft,
    TripRequest,
    create_approval,
)
from src.governance.audit_v1 import build_audit_bundle
from src.governance.evals_v1 import evaluate_proposal
from src.intake.abacus_webform_v1 import (
    AbacusWebFormPayload,
    CanonicalCompletion,
    migrate_abacus_payload,
)

router = APIRouter(prefix="/v1", tags=["contract-v1"])


class ContractInfo(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    external_side_effects: bool = False
    approval_auth: str = "bearer-owner-token"


class NormalizeAbacusRequest(BaseModel):
    payload: AbacusWebFormPayload
    completion: Optional[CanonicalCompletion] = None


class NormalizeAbacusResponse(BaseModel):
    status: Literal["READY_FOR_SEARCH", "NEEDS_INFORMATION"]
    trip_request: Optional[TripRequest] = None
    missing_fields: List[str] = Field(default_factory=list)
    legacy_budget_label: Optional[str] = None


class EvaluateProposalRequest(BaseModel):
    trip_request: TripRequest
    evidence_pack: EvidencePack
    proposal: ProposalDraft


class ApproveProposalRequest(EvaluateProposalRequest):
    comment: Optional[str] = Field(default=None, max_length=4000)
    final_output: Optional[str] = None
    system_version: str = Field(default="1.0.0", min_length=1, max_length=200)
    agent_release_id: str = Field(default="travel-agent-contract-v1", min_length=1, max_length=200)


class ApproveProposalResponse(BaseModel):
    eval_result: EvalResult
    approval: ApprovalRecord
    audit_bundle: AuditBundle


def _require_agent_identity(authorization: Optional[str], agent_id: Optional[str]) -> str:
    expected = os.getenv("OWNER_APPROVAL_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="approval endpoint is disabled until OWNER_APPROVAL_TOKEN is configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer approval token")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="invalid approval token")
    if not agent_id or not agent_id.strip():
        raise HTTPException(status_code=400, detail="X-Agent-Id is required")
    return agent_id.strip()


@router.get("/contract", response_model=ContractInfo)
def contract_info() -> ContractInfo:
    return ContractInfo()


@router.post("/intake/abacus/normalize", response_model=NormalizeAbacusResponse)
def normalize_abacus(req: NormalizeAbacusRequest) -> NormalizeAbacusResponse:
    result = migrate_abacus_payload(req.payload, req.completion)
    if not result.is_complete:
        return NormalizeAbacusResponse(
            status="NEEDS_INFORMATION",
            missing_fields=result.missing_fields,
            legacy_budget_label=result.legacy_budget_label,
        )
    return NormalizeAbacusResponse(
        status="READY_FOR_SEARCH",
        trip_request=result.canonical_request,
        legacy_budget_label=result.legacy_budget_label,
    )


@router.post("/proposals/evaluate", response_model=EvalResult)
def evaluate(req: EvaluateProposalRequest) -> EvalResult:
    return evaluate_proposal(req.trip_request, req.evidence_pack, req.proposal)


@router.post("/proposals/approve", response_model=ApproveProposalResponse)
def approve(
    req: ApproveProposalRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    agent_id: Optional[str] = Header(default=None, alias="X-Agent-Id"),
) -> ApproveProposalResponse:
    identity = _require_agent_identity(authorization, agent_id)
    eval_result = evaluate_proposal(req.trip_request, req.evidence_pack, req.proposal)
    if not eval_result.can_approve:
        failed = [check.check_id for check in eval_result.checks if check.status.value == "FAIL"]
        raise HTTPException(
            status_code=409,
            detail={"message": "proposal failed eval gate", "failed_checks": failed},
        )

    try:
        approval = create_approval(
            req.proposal,
            eval_result,
            agent_id=identity,
            comment=req.comment,
        )
        audit = build_audit_bundle(
            req.trip_request,
            req.evidence_pack,
            req.proposal,
            eval_result,
            approval=approval,
            final_output=req.final_output,
            system_version=req.system_version,
            agent_release_id=req.agent_release_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ApproveProposalResponse(
        eval_result=eval_result,
        approval=approval,
        audit_bundle=audit,
    )
