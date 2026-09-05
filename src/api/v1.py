"""Contract v1 API surface.

Mutation and delivery actions remain fail-closed. Read-only provider search and
model planning are independently gated runtime capabilities.
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
from src.core import config
from src.governance.audit_v1 import build_audit_bundle
from src.governance.evals_v1 import evaluate_proposal
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion, migrate_abacus_payload
from src.providers.serpapi_client_v1 import SerpApiClientV1
from src.runtime.planner_v1 import GeminiPlannerV1, build_proposal_draft
from src.runtime.provider_diagnostics import log_provider_failure
from src.runtime.workflow_v1 import WebDraftWorkflowResult, run_web_draft_workflow

router = APIRouter(prefix="/v1", tags=["contract-v1"])


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _model_planner():
    if not _env_enabled("V1_MODEL_PLANNER_ENABLED") or not config.GEMINI_API_KEY:
        return None
    from google import genai
    return GeminiPlannerV1(genai.Client(api_key=config.GEMINI_API_KEY), config.GEMINI_MODEL)


def _evidence_searcher():
    if not _env_enabled("V1_LIVE_SEARCH_ENABLED") or not config.SERPAPI_KEY:
        return None
    return SerpApiClientV1(config.SERPAPI_KEY)


class ContractInfo(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    external_side_effects: bool = False
    approval_auth: str = "bearer-owner-token"
    live_search_enabled: bool = False
    model_planner_enabled: bool = False


class NormalizeAbacusRequest(BaseModel):
    payload: AbacusWebFormPayload
    completion: Optional[CanonicalCompletion] = None


class NormalizeAbacusResponse(BaseModel):
    status: Literal["READY_FOR_SEARCH", "NEEDS_INFORMATION"]
    trip_request: Optional[TripRequest] = None
    missing_fields: List[str] = Field(default_factory=list)
    legacy_budget_label: Optional[str] = None


class WebDraftRequest(BaseModel):
    payload: AbacusWebFormPayload
    completion: Optional[CanonicalCompletion] = None
    origin_iata: Optional[str] = Field(default=None, min_length=3, max_length=3)
    destination_iata: Optional[str] = Field(default=None, min_length=3, max_length=3)


class EvidenceSearchRequest(BaseModel):
    trip_request: TripRequest
    origin_iata: str = Field(..., min_length=3, max_length=3)
    destination_iata: str = Field(..., min_length=3, max_length=3)


class EvidenceSearchResponse(BaseModel):
    evidence_pack: EvidencePack


class GenerateProposalRequest(BaseModel):
    trip_request: TripRequest
    evidence_pack: EvidencePack


class GenerateProposalResponse(BaseModel):
    proposal: ProposalDraft
    planner_used: bool


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
        raise HTTPException(status_code=503, detail="approval endpoint is disabled until OWNER_APPROVAL_TOKEN is configured")
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
    return ContractInfo(
        live_search_enabled=_env_enabled("V1_LIVE_SEARCH_ENABLED"),
        model_planner_enabled=_env_enabled("V1_MODEL_PLANNER_ENABLED"),
    )


@router.post("/intake/abacus/normalize", response_model=NormalizeAbacusResponse)
def normalize_abacus(req: NormalizeAbacusRequest) -> NormalizeAbacusResponse:
    result = migrate_abacus_payload(req.payload, req.completion)
    if not result.is_complete:
        return NormalizeAbacusResponse(status="NEEDS_INFORMATION", missing_fields=result.missing_fields, legacy_budget_label=result.legacy_budget_label)
    return NormalizeAbacusResponse(status="READY_FOR_SEARCH", trip_request=result.canonical_request, legacy_budget_label=result.legacy_budget_label)


@router.post("/web/draft", response_model=WebDraftWorkflowResult)
def web_draft(req: WebDraftRequest) -> WebDraftWorkflowResult:
    try:
        planner = _model_planner()
    except Exception as exc:
        log_provider_failure("gemini_init", exc, model=config.GEMINI_MODEL)
        planner = None
    return run_web_draft_workflow(
        req.payload,
        req.completion,
        origin_iata=req.origin_iata,
        destination_iata=req.destination_iata,
        evidence_searcher=_evidence_searcher(),
        planner=planner,
        model_version=config.GEMINI_MODEL if planner is not None else "planner-disabled",
    )


@router.post("/evidence/search", response_model=EvidenceSearchResponse)
def search_evidence(req: EvidenceSearchRequest) -> EvidenceSearchResponse:
    searcher = _evidence_searcher()
    if searcher is None:
        if not _env_enabled("V1_LIVE_SEARCH_ENABLED"):
            raise HTTPException(status_code=503, detail="Contract v1 live search is disabled")
        raise HTTPException(status_code=503, detail="SERPAPI_API_KEY is not configured")
    try:
        pack = searcher.search_evidence(req.trip_request, origin_iata=req.origin_iata, destination_iata=req.destination_iata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="read-only provider search failed") from exc
    return EvidenceSearchResponse(evidence_pack=pack)


@router.post("/proposals/generate", response_model=GenerateProposalResponse)
def generate_proposal(req: GenerateProposalRequest) -> GenerateProposalResponse:
    planner_enabled = _env_enabled("V1_MODEL_PLANNER_ENABLED")
    narrative = None
    model_version = "planner-disabled"
    if planner_enabled:
        if not config.GEMINI_API_KEY:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured for Contract v1 planner")
        try:
            planner = _model_planner()
            if planner is None:
                raise ValueError("planner is unavailable")
            narrative = planner.generate_narrative(req.trip_request, req.evidence_pack)
            model_version = config.GEMINI_MODEL
        except ValueError as exc:
            log_provider_failure("gemini", exc, request_id=req.trip_request.request_id, model=config.GEMINI_MODEL)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            log_provider_failure("gemini", exc, request_id=req.trip_request.request_id, model=config.GEMINI_MODEL)
            proposal = build_proposal_draft(req.trip_request, req.evidence_pack, narrative=None, model_version=config.GEMINI_MODEL)
            proposal.warnings.append("Planner model failed; returning partial evidence-only draft.")
            return GenerateProposalResponse(proposal=proposal, planner_used=False)
    try:
        proposal = build_proposal_draft(req.trip_request, req.evidence_pack, narrative=narrative, model_version=model_version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GenerateProposalResponse(proposal=proposal, planner_used=narrative is not None)


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
        raise HTTPException(status_code=409, detail={"message": "proposal failed eval gate", "failed_checks": failed})
    try:
        approval = create_approval(req.proposal, eval_result, agent_id=identity, comment=req.comment)
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
    return ApproveProposalResponse(eval_result=eval_result, approval=approval, audit_bundle=audit)
