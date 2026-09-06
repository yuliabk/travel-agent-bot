"""Contract v1 API surface.

Mutation and delivery actions remain fail-closed. Read-only provider search and
model planning are independently gated runtime capabilities.
"""

from __future__ import annotations

import hmac
import os
import math
import re
from concurrent.futures import ThreadPoolExecutor
import requests
from typing import List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.capabilities.flight_search_v1 import FlightSearchConsumerV1
from src.contracts.travel_v1 import (
    ApprovalRecord,
    AuditBundle,
    EvalResult,
    EvidencePack,
    EvidenceType,
    ProposalDraft,
    TripRequest,
    StaySegment,
    create_approval,
)
from src.core import config
from src.governance.audit_v1 import build_audit_bundle
from src.governance.evals_v1 import evaluate_proposal
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion, migrate_abacus_payload
from src.providers.serpapi_client_v1 import SerpApiClientV1
from src.runtime.flight_capability_runtime_v1 import SandboxFlightCapabilityInvokerV1
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


def _flight_bridge_enabled() -> bool:
    return os.getenv("V1_CORE_FLIGHT_SANDBOX_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _flight_search():
    if not _flight_bridge_enabled():
        return None
    return FlightSearchConsumerV1(SandboxFlightCapabilityInvokerV1())


class ContractInfo(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    external_side_effects: bool = False
    approval_auth: str = "bearer-owner-token"
    live_search_enabled: bool = False
    governed_flight_search_enabled: bool = False
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
    stays: List[StaySegment] = Field(default_factory=list, max_length=6)
    alternative_airports: List[str] = Field(default_factory=list, max_length=3)


class MapPointsRequest(BaseModel):
    destination: str = Field(default="", max_length=200)
    places: List[str] = Field(..., min_length=1, max_length=40)


class DestinationLookupRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)


@router.post("/web/destinations")
def destination_lookup(req: DestinationLookupRequest):
    if not config.SERPAPI_KEY:
        raise HTTPException(status_code=503, detail="שירות זיהוי היעדים אינו זמין כרגע")
    try:
        data = SerpApiClientV1(config.SERPAPI_KEY, timeout=10)._get({
            "engine": "google_flights_autocomplete", "q": req.query.strip(),
            "exclude_regions": "true", "hl": "iw", "api_key": config.SERPAPI_KEY,
        })
        suggestions = []
        for item in (data.get("suggestions") or [])[:6]:
            if item.get("type") != "city" or not item.get("name"):
                continue
            airports = [{"code": airport["id"], "name": str(airport.get("name") or airport["id"])} for airport in item.get("airports", []) if re.fullmatch(r"[A-Z]{3}", str(airport.get("id", "")))]
            suggestions.append({"name": str(item["name"]), "description": str(item.get("description") or ""), "airports": airports})
        return {"suggestions": suggestions}
    except Exception as exc:
        log_provider_failure("destination_lookup", exc)
        raise HTTPException(status_code=502, detail="זיהוי היעד נכשל. נסו שם עיר באנגלית עם שם המדינה.") from exc


@router.post("/web/map-points")
def map_points(req: MapPointsRequest):
    if not config.SERPAPI_KEY:
        raise HTTPException(status_code=503, detail="Map service unavailable")
    names = list(dict.fromkeys(name.strip() for name in req.places if name.strip()))
    if any(len(name) > 300 for name in names):
        raise HTTPException(status_code=422, detail="Place name too long")

    def locate(name):
        try:
            # Prefer the official local name inside a bilingual display label.
            local_names = re.findall(r"\(([^()]*[A-Za-z][^()]*)\)", name)
            query_name = local_names[-1] if local_names else name
            response = requests.get("https://serpapi.com/search.json", params={
                "engine": "google_maps", "type": "search", "q": f"{query_name}, {req.destination}",
                "hl": "iw", "api_key": config.SERPAPI_KEY,
            }, timeout=(3, 5))
            response.raise_for_status()
            data = response.json()
            place = data.get("place_results") or next((item for item in (data.get("local_results") or []) if isinstance(item, dict) and item.get("gps_coordinates")), {})
            gps = place.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if all(type(n) in (int, float) and math.isfinite(n) for n in (lat, lng)) and -90 <= lat <= 90 and -180 <= lng <= 180:
                return {"name": name, "lat": lat, "lng": lng}
        except Exception as exc:
            log_provider_failure("map_geocoding", exc)
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(locate, names))
    return {"points": [point for point in results if point], "missing": [name for name, point in zip(names, results) if not point]}


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
        governed_flight_search_enabled=_flight_bridge_enabled(),
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
        flight_search=_flight_search(),
        planner=planner,
        model_version=config.GEMINI_MODEL if planner is not None else "planner-disabled",
        stays=req.stays,
        alternative_airports=req.alternative_airports,
    )


@router.post("/evidence/search", response_model=EvidenceSearchResponse)
def search_evidence(req: EvidenceSearchRequest) -> EvidenceSearchResponse:
    pack = EvidencePack(request_id=req.trip_request.request_id)
    searcher = _evidence_searcher()
    if searcher is not None:
        try:
            pack = searcher.search_evidence(req.trip_request, origin_iata=req.origin_iata, destination_iata=req.destination_iata)
        except Exception as exc:
            log_provider_failure("serpapi", exc, request_id=req.trip_request.request_id)

    flight_search = _flight_search()
    if flight_search is not None:
        try:
            flights = flight_search.search_flights(
                req.trip_request,
                origin_iata=req.origin_iata,
                destination_iata=req.destination_iata,
            )
            if flights:
                pack.records = [record for record in pack.records if record.type != EvidenceType.FLIGHT]
                pack.records.extend(flights)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            log_provider_failure("flight_capability", exc, request_id=req.trip_request.request_id)

    if searcher is None and flight_search is None:
        raise HTTPException(status_code=503, detail="Contract v1 live evidence search is disabled")
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
