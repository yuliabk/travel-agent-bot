"""Provider-neutral consumer for the Agent Factory `research.lookup@1` capability."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Mapping, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.contracts.travel_v1 import (
    EvidenceRecord,
    EvidenceSourceStatus,
    EvidenceType,
    TripRequest,
)


RESEARCH_LOOKUP_REF = "research.lookup"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ResearchLookupRequest(StrictModel):
    query: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    freshness: Literal["any", "recent", "current"] = "any"
    max_evidence_items: int = Field(default=6, alias="maxEvidenceItems", ge=1, le=20)


class ResearchFinding(StrictModel):
    statement: str = Field(..., min_length=1)
    evidence_ids: List[str] = Field(default_factory=list, alias="evidenceIds")


class ResearchEvidence(StrictModel):
    id: str = Field(..., min_length=1)
    source_type: Literal["internal", "web", "api", "capability", "model"] = Field(alias="sourceType")
    source_ref: str = Field(..., alias="sourceRef", min_length=1)
    title: Optional[str] = None
    summary: str = Field(..., min_length=1)
    retrieved_at: Optional[datetime] = Field(default=None, alias="retrievedAt")


class ResearchLookupResponse(StrictModel):
    status: Literal["complete", "partial", "unavailable"]
    answer: str = Field(..., min_length=1)
    findings: List[ResearchFinding] = Field(default_factory=list)
    evidence: List[ResearchEvidence] = Field(default_factory=list, max_length=20)
    limitations: List[str] = Field(default_factory=list)


class CapabilityInvoker(Protocol):
    def invoke(self, capability_ref: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Invoke a capability selected by Core/runtime policy, not by Travel business code."""


class ResearchLookupConsumerV1:
    """Translate a Travel request into minimized research.lookup input and Travel evidence."""

    def __init__(self, capability_invoker: CapabilityInvoker, *, max_evidence_items: int = 6) -> None:
        if not 1 <= max_evidence_items <= 20:
            raise ValueError("max_evidence_items must be between 1 and 20")
        self.capability_invoker = capability_invoker
        self.max_evidence_items = max_evidence_items

    def build_request(self, request: TripRequest) -> ResearchLookupRequest:
        # Intentionally excludes customer name/email/phone and commercial budget.
        context_parts = [f"Destination: {request.destination}"]
        if request.preferences.interests:
            context_parts.append("Interests: " + ", ".join(request.preferences.interests[:8]))
        if request.preferences.preferred_areas:
            context_parts.append("Preferred areas: " + ", ".join(request.preferences.preferred_areas[:8]))
        if request.preferences.constraints:
            context_parts.append("Travel constraints: " + ", ".join(request.preferences.constraints[:8]))

        return ResearchLookupRequest(
            query=". ".join(context_parts) + ". Provide useful background for itinerary planning.",
            purpose="travel itinerary background research",
            freshness="any",
            maxEvidenceItems=self.max_evidence_items,
        )

    def lookup(self, request: TripRequest) -> ResearchLookupResponse:
        capability_request = self.build_request(request)
        raw = self.capability_invoker.invoke(
            RESEARCH_LOOKUP_REF,
            capability_request.model_dump(by_alias=True, mode="json"),
        )
        return ResearchLookupResponse.model_validate(dict(raw))

    def search_background(self, request: TripRequest) -> List[EvidenceRecord]:
        result = self.lookup(request)
        records: List[EvidenceRecord] = []
        for item in result.evidence:
            normalized: Dict[str, Any] = {
                "research_evidence_id": item.id,
                "source_type": item.source_type,
                "title": item.title,
                "summary": item.summary,
                "source_ref": item.source_ref,
                "research_status": result.status,
                "research_limitations": list(result.limitations),
            }
            records.append(
                EvidenceRecord(
                    type=EvidenceType.PLACE,
                    provider=RESEARCH_LOOKUP_REF,
                    provider_reference=item.source_ref[:500],
                    source_status=EvidenceSourceStatus.UNVERIFIED,
                    raw_reference=item.source_ref[:1000],
                    normalized_data=normalized,
                )
            )
        return records
