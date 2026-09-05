"""Unified Contract v1 draft workflow used by Web and future channels."""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.contracts.travel_v1 import EvidencePack, ProposalDraft
from src.intake.abacus_webform_v1 import AbacusWebFormPayload, CanonicalCompletion, migrate_abacus_payload
from src.runtime.planner_v1 import build_proposal_draft
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
    planner: Optional[Any] = None,
    model_version: str = "planner-disabled",
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
    pack = EvidencePack(request_id=request.request_id)
    workflow_warnings: List[str] = []

    if evidence_searcher is not None and origin_iata and destination_iata:
        try:
            pack = evidence_searcher.search_evidence(
                request,
                origin_iata=origin_iata,
                destination_iata=destination_iata,
            )
        except Exception:
            workflow_warnings.append("Live commercial evidence search failed; commercial results may be incomplete.")
    else:
        workflow_warnings.append("Live commercial evidence search was not executed.")

    narrative = None
    if planner is not None:
        try:
            narrative = planner.generate_narrative(request, pack)
        except Exception:
            workflow_warnings.append("Planner model failed; returning an evidence-only partial draft.")

    proposal = build_proposal_draft(
        request,
        pack,
        narrative=narrative,
        model_version=model_version,
    )
    proposal.warnings.extend(workflow_warnings)
    rendered = render_ai_draft_hebrew(request, proposal)

    return WebDraftWorkflowResult(
        status="AI_DRAFT" if narrative is not None else "PARTIAL_DRAFT",
        evidence_pack=pack,
        proposal=proposal,
        rendered_draft=rendered,
    )
