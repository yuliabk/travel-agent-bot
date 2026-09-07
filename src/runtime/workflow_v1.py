"""Unified Contract v1 draft workflow used by Web and future channels."""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.contracts.travel_v1 import EvidencePack, EvidenceType, ProposalDraft, TripRequest, StaySegment
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion, migrate_abacus_payload
from src.runtime.planner_v1 import build_proposal_draft
from src.runtime.provider_diagnostics import log_provider_failure
from src.runtime.renderer_v1 import render_ai_draft_hebrew


class WebDraftWorkflowResult(BaseModel):
    status: Literal["NEEDS_INFORMATION", "PARTIAL_DRAFT", "AI_DRAFT"]
    missing_fields: List[str] = Field(default_factory=list)
    evidence_pack: Optional[EvidencePack] = None
    proposal: Optional[ProposalDraft] = None
    rendered_draft: Optional[str] = None


def run_web_draft_workflow(
    payload: AbacusWebFormPayload,
    completion: Optional[CanonicalCompletion],
    *,
    origin_iata: Optional[str] = None,
    destination_iata: Optional[str] = None,
    evidence_searcher: Optional[Any] = None,
    flight_search: Optional[Any] = None,
    research_lookup: Optional[Any] = None,
    rental_car_search: Optional[Any] = None,
    attraction_lookup: Optional[Any] = None,
    planner: Optional[Any] = None,
    model_version: str = "planner-disabled",
    stays: Optional[List[StaySegment]] = None,
    alternative_airports: Optional[List[str]] = None,
) -> WebDraftWorkflowResult:
    """Run intake -> optional evidence -> optional narrative -> render.

    Dependencies are injected so tests never require network/model calls.
    Missing dependencies yield an explicit partial draft rather than invented data.
    """
    migration = migrate_abacus_payload(payload, completion)
    if not migration.is_complete or migration.canonical_request is None:
        return WebDraftWorkflowResult(
            status="NEEDS_INFORMATION",
            missing_fields=migration.missing_fields,
        )

    request = migration.canonical_request
    if stays or destination_iata:
        try:
            request = TripRequest.model_validate({**request.model_dump(), "stays": stays or [], "arrival_airport": destination_iata.upper() if destination_iata else None})
        except ValueError:
            return WebDraftWorkflowResult(status="NEEDS_INFORMATION", missing_fields=["stays"])
    if (evidence_searcher is not None or flight_search is not None) and (not origin_iata or not destination_iata):
        return WebDraftWorkflowResult(
            status="NEEDS_INFORMATION",
            missing_fields=[name for name, value in (
                ("origin_iata", origin_iata), ("destination_iata", destination_iata)
            ) if not value],
        )
    pack = EvidencePack(request_id=request.request_id)
    workflow_warnings: List[str] = []

    if evidence_searcher is not None and origin_iata and destination_iata:
        try:
            pack = evidence_searcher.search_evidence(
                request,
                origin_iata=origin_iata,
                destination_iata=destination_iata,
                **({"alternative_airports": alternative_airports} if alternative_airports else {}),
            )
        except Exception as exc:
            log_provider_failure("serpapi", exc, request_id=request.request_id)
            workflow_warnings.append("Live commercial evidence search failed; commercial results may be incomplete.")
    elif flight_search is None:
        workflow_warnings.append("Live commercial evidence search was not executed.")

    if flight_search is not None and origin_iata and destination_iata:
        try:
            flights = flight_search.search_flights(
                request,
                origin_iata=origin_iata,
                destination_iata=destination_iata,
            )
            if flights:
                pack.records = [record for record in pack.records if record.type != EvidenceType.FLIGHT]
                pack.records.extend(flights)
            else:
                workflow_warnings.append("Governed flight search returned no observed options.")
        except Exception as exc:
            log_provider_failure("flight_capability", exc, request_id=request.request_id)
            workflow_warnings.append("Governed flight search capability failed; flight results may be incomplete.")

    if flight_search is not None and evidence_searcher is None:
        workflow_warnings.append("Hotel commercial evidence search was not executed.")

    if payload.carRental and rental_car_search is not None:
        try:
            rentals = rental_car_search.search_rental_cars(request)
            pack.records.extend(rentals)
            if not rentals:
                workflow_warnings.append("Open rental-car search returned no observed quotes.")
        except Exception as exc:
            log_provider_failure("rental_car_search", exc, request_id=request.request_id)
            workflow_warnings.append("חיפוש מחירי הרכב השכור לא הושלם.")
    elif payload.carRental:
        workflow_warnings.append("חיפוש רכב שכור התבקש אך ספק מחירים אינו זמין כרגע.")

    if research_lookup is not None:
        try:
            pack.records.extend(research_lookup.search_background(request))
        except Exception as exc:
            log_provider_failure("research_lookup", exc, request_id=request.request_id)
            workflow_warnings.append("Background research capability failed; itinerary context may be incomplete.")

    narrative = None
    if planner is not None:
        try:
            narrative = planner.generate_narrative(request, pack)
        except Exception as exc:
            log_provider_failure("gemini", exc, request_id=request.request_id, model=model_version)
            workflow_warnings.append("Planner model failed; returning an evidence-only partial draft.")

    if narrative is not None and evidence_searcher is not None:
        enrich = getattr(evidence_searcher, "search_attraction_prices", None)
        if callable(enrich):
            try:
                pack.records.extend(enrich(request, narrative))
            except Exception as exc:
                log_provider_failure("attraction_search", exc, request_id=request.request_id)
                workflow_warnings.append("חיפוש מחירי האטרקציות לא הושלם. עלויות חסרות אינן אפס.")

    if narrative is not None and attraction_lookup is not None:
        try:
            existing = {
                (str(record.normalized_data.get("name") or "").casefold(), str(record.normalized_data.get("city") or "").casefold())
                for record in pack.records
                if record.type == EvidenceType.PLACE and record.normalized_data.get("kind") == "attraction"
            }
            open_records = attraction_lookup.search_attractions(request, narrative)
            pack.records.extend(
                record for record in open_records
                if (str(record.normalized_data.get("name") or "").casefold(), str(record.normalized_data.get("city") or "").casefold()) not in existing
            )
        except Exception as exc:
            log_provider_failure("open_attraction_lookup", exc, request_id=request.request_id)
            workflow_warnings.append("חיפוש המידע הפתוח על האטרקציות לא הושלם.")

    proposal = build_proposal_draft(
        request,
        pack,
        narrative=narrative,
        model_version=model_version,
    )
    proposal.warnings.extend(workflow_warnings)
    proposal.warnings.extend(pack.search_notes)
    rendered = render_ai_draft_hebrew(request, proposal)

    return WebDraftWorkflowResult(
        status="AI_DRAFT" if narrative is not None else "PARTIAL_DRAFT",
        evidence_pack=pack,
        proposal=proposal,
        rendered_draft=rendered,
    )
