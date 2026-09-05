"""Canonical Travel Agent Instance Contract v1.

This module is intentionally side-effect free. It defines the versioned data
contracts and deterministic validation helpers shared by Web, Email and
WhatsApp once those channels are migrated to the unified runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, model_validator

SCHEMA_VERSION_V1 = "1.0.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ContractModel(BaseModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION_V1


class CreatedByType(str, Enum):
    CUSTOMER = "customer"
    AGENT = "agent"


class ConsentStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


class TripRequestStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    READY_FOR_SEARCH = "READY_FOR_SEARCH"


class FlightRoutingPreference(str, Enum):
    NONSTOP = "nonstop"
    ONE_STOP = "one_stop"
    ANY = "any"


class ChildTraveler(BaseModel):
    age: int = Field(..., ge=0, le=17)


class TravelerParty(BaseModel):
    adults: int = Field(default=1, ge=1, le=20)
    children: List[ChildTraveler] = Field(default_factory=list)


class CustomerContact(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=5, max_length=40)

    @model_validator(mode="after")
    def require_contact_channel(self) -> "CustomerContact":
        if not self.email and not self.phone:
            raise ValueError("at least one customer contact channel (email or phone) is required")
        return self


class TripPreferences(BaseModel):
    flight_routing: FlightRoutingPreference = FlightRoutingPreference.ANY
    baggage: Optional[str] = Field(default=None, max_length=500)
    hotel_level: Optional[str] = Field(default=None, max_length=200)
    preferred_areas: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=4000)


class TripRequest(ContractModel):
    request_id: str = Field(default_factory=lambda: new_id("req"), min_length=8)
    created_at: datetime = Field(default_factory=utc_now)
    created_by_type: CreatedByType
    status: TripRequestStatus = TripRequestStatus.DRAFT
    customer: CustomerContact
    origin: str = Field(..., min_length=2, max_length=200)
    destination: str = Field(..., min_length=2, max_length=200)
    departure_date: date
    return_date: date
    travelers: TravelerParty = Field(default_factory=TravelerParty)
    budget: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    consent_status: ConsentStatus

    @model_validator(mode="after")
    def validate_trip_window(self) -> "TripRequest":
        if self.return_date < self.departure_date:
            raise ValueError("return_date must be on or after departure_date")
        return self


class EvidenceType(str, Enum):
    FLIGHT = "FLIGHT"
    HOTEL = "HOTEL"
    PLACE = "PLACE"
    TRANSPORT = "TRANSPORT"
    PRICE = "PRICE"


class EvidenceSourceStatus(str, Enum):
    VERIFIED = "verified"
    ESTIMATE = "estimate"
    TEST = "test"
    EVALUATION = "evaluation"
    STALE = "stale"
    UNVERIFIED = "unverified"


class EvidenceRecord(ContractModel):
    evidence_id: str = Field(default_factory=lambda: new_id("ev"), min_length=8)
    type: EvidenceType
    provider: str = Field(..., min_length=1, max_length=100)
    provider_reference: Optional[str] = Field(default=None, max_length=500)
    searched_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    amount: Optional[Decimal] = Field(default=None, ge=0)
    source_status: EvidenceSourceStatus
    raw_reference: Optional[str] = Field(default=None, max_length=1000)
    normalized_data: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_price_traceability(self) -> "EvidenceRecord":
        if (self.amount is None) != (self.currency is None):
            raise ValueError("amount and currency must be supplied together")
        if self.source_status == EvidenceSourceStatus.VERIFIED:
            if self.amount is None or not self.currency or not self.provider_reference:
                raise ValueError("verified evidence requires amount, currency and provider_reference")
            if self.missing_fields:
                raise ValueError("verified evidence cannot declare missing_fields")
        if self.expires_at and self.expires_at < self.searched_at:
            raise ValueError("expires_at cannot precede searched_at")
        return self

    @property
    def is_verified_price(self) -> bool:
        return (
            self.source_status == EvidenceSourceStatus.VERIFIED
            and self.amount is not None
            and self.currency is not None
            and bool(self.provider_reference)
        )


class EvidencePack(ContractModel):
    evidence_pack_id: str = Field(default_factory=lambda: new_id("ep"), min_length=8)
    request_id: str
    created_at: datetime = Field(default_factory=utc_now)
    records: List[EvidenceRecord] = Field(default_factory=list)

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return next((record for record in self.records if record.evidence_id == evidence_id), None)


class ProposalStatus(str, Enum):
    AI_DRAFT = "AI_DRAFT"
    PARTIAL_DRAFT = "PARTIAL_DRAFT"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"


class MoneyAmount(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    is_estimate: bool = True


class ProposalDraft(ContractModel):
    proposal_id: str = Field(default_factory=lambda: new_id("prop"), min_length=8)
    request_id: str
    version: int = Field(default=1, ge=1)
    status: ProposalStatus = ProposalStatus.AI_DRAFT
    created_at: datetime = Field(default_factory=utc_now)
    model_version: str = Field(..., min_length=1, max_length=200)
    evidence_pack_id: str
    summary: str = ""
    flight_options: List[Dict[str, Any]] = Field(default_factory=list)
    hotel_options: List[Dict[str, Any]] = Field(default_factory=list)
    daily_itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_total: List[MoneyAmount] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_partial_state(self) -> "ProposalDraft":
        if self.status in {ProposalStatus.PARTIAL_DRAFT, ProposalStatus.NEEDS_INFORMATION}:
            if not self.missing_information:
                raise ValueError(f"{self.status.value} requires missing_information")
        return self


class EvalCheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class EvalOverallStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class EvalCheck(BaseModel):
    check_id: str = Field(..., min_length=1, max_length=100)
    status: EvalCheckStatus
    message: str = ""


class EvalResult(ContractModel):
    eval_id: str = Field(default_factory=lambda: new_id("eval"), min_length=8)
    proposal_id: str
    proposal_version: int = Field(..., ge=1)
    evaluated_at: datetime = Field(default_factory=utc_now)
    overall_status: EvalOverallStatus
    checks: List[EvalCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_overall_status(self) -> "EvalResult":
        statuses = {check.status for check in self.checks}
        if EvalCheckStatus.FAIL in statuses and self.overall_status != EvalOverallStatus.FAIL:
            raise ValueError("overall_status must be FAIL when any eval check fails")
        if EvalCheckStatus.FAIL not in statuses and EvalCheckStatus.WARN in statuses:
            if self.overall_status != EvalOverallStatus.PASS_WITH_WARNINGS:
                raise ValueError("warnings require PASS_WITH_WARNINGS")
        if statuses and statuses <= {EvalCheckStatus.PASS} and self.overall_status != EvalOverallStatus.PASS:
            raise ValueError("all-pass checks require overall_status PASS")
        return self

    @property
    def can_approve(self) -> bool:
        return self.overall_status in {EvalOverallStatus.PASS, EvalOverallStatus.PASS_WITH_WARNINGS}


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ApprovalRecord(ContractModel):
    approval_id: str = Field(default_factory=lambda: new_id("approval"), min_length=8)
    proposal_id: str
    proposal_version: int = Field(..., ge=1)
    proposal_hash: str
    agent_id: str = Field(..., min_length=1, max_length=200)
    decision: ApprovalDecision
    decided_at: datetime = Field(default_factory=utc_now)
    comment: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_hash(self) -> "ApprovalRecord":
        if not _SHA256_RE.fullmatch(self.proposal_hash):
            raise ValueError("proposal_hash must be a lowercase SHA-256 hex digest")
        return self

    def is_valid_for(self, proposal: ProposalDraft) -> bool:
        return (
            self.decision == ApprovalDecision.APPROVED
            and self.proposal_id == proposal.proposal_id
            and self.proposal_version == proposal.version
            and self.proposal_hash == canonical_hash(proposal)
        )


class AuditUsage(BaseModel):
    model_calls: int = Field(default=0, ge=0)
    provider_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: Optional[Decimal] = Field(default=None, ge=0)
    cost_currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_cost_pair(self) -> "AuditUsage":
        if (self.estimated_cost is None) != (self.cost_currency is None):
            raise ValueError("estimated_cost and cost_currency must be supplied together")
        return self


class AuditBundle(ContractModel):
    audit_bundle_id: str = Field(default_factory=lambda: new_id("audit"), min_length=8)
    request_id: str
    proposal_id: str
    proposal_version: int = Field(..., ge=1)
    request_hash: str
    evidence_pack_id: str
    evidence_pack_hash: str
    proposal_hash: str
    eval_id: str
    approval_id: Optional[str] = None
    final_output_hash: Optional[str] = None
    system_version: str = Field(..., min_length=1, max_length=200)
    agent_release_id: str = Field(..., min_length=1, max_length=200)
    usage: AuditUsage = Field(default_factory=AuditUsage)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_hashes(self) -> "AuditBundle":
        for name in ("request_hash", "evidence_pack_hash", "proposal_hash"):
            value = getattr(self, name)
            if not _SHA256_RE.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
        if self.final_output_hash and not _SHA256_RE.fullmatch(self.final_output_hash):
            raise ValueError("final_output_hash must be a lowercase SHA-256 hex digest")
        return self


def canonical_hash(model: BaseModel) -> str:
    """Return a deterministic SHA-256 digest for a Pydantic model snapshot."""
    payload = model.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_approval(
    proposal: ProposalDraft,
    eval_result: EvalResult,
    *,
    agent_id: str,
    comment: Optional[str] = None,
) -> ApprovalRecord:
    """Create an approval only when the exact proposal version passed evals."""
    if eval_result.proposal_id != proposal.proposal_id:
        raise ValueError("eval_result does not belong to proposal")
    if eval_result.proposal_version != proposal.version:
        raise ValueError("eval_result does not belong to proposal version")
    if not eval_result.can_approve:
        raise ValueError("proposal cannot be approved while eval status is FAIL")
    if proposal.status != ProposalStatus.READY_FOR_REVIEW:
        raise ValueError("proposal must be READY_FOR_REVIEW before approval")
    return ApprovalRecord(
        proposal_id=proposal.proposal_id,
        proposal_version=proposal.version,
        proposal_hash=canonical_hash(proposal),
        agent_id=agent_id,
        decision=ApprovalDecision.APPROVED,
        comment=comment,
    )


TRIP_REQUEST_TRANSITIONS = {
    TripRequestStatus.DRAFT: {TripRequestStatus.SUBMITTED},
    TripRequestStatus.SUBMITTED: {TripRequestStatus.NEEDS_INFORMATION, TripRequestStatus.READY_FOR_SEARCH},
    TripRequestStatus.NEEDS_INFORMATION: {TripRequestStatus.SUBMITTED},
    TripRequestStatus.READY_FOR_SEARCH: set(),
}

PROPOSAL_TRANSITIONS = {
    ProposalStatus.AI_DRAFT: {
        ProposalStatus.PARTIAL_DRAFT,
        ProposalStatus.NEEDS_INFORMATION,
        ProposalStatus.READY_FOR_REVIEW,
        ProposalStatus.SUPERSEDED,
    },
    ProposalStatus.PARTIAL_DRAFT: {
        ProposalStatus.NEEDS_INFORMATION,
        ProposalStatus.READY_FOR_REVIEW,
        ProposalStatus.SUPERSEDED,
    },
    ProposalStatus.NEEDS_INFORMATION: {
        ProposalStatus.PARTIAL_DRAFT,
        ProposalStatus.READY_FOR_REVIEW,
        ProposalStatus.SUPERSEDED,
    },
    ProposalStatus.READY_FOR_REVIEW: {ProposalStatus.APPROVED, ProposalStatus.SUPERSEDED},
    ProposalStatus.APPROVED: {ProposalStatus.SUPERSEDED},
    ProposalStatus.SUPERSEDED: set(),
}


def validate_trip_request_transition(current: TripRequestStatus, target: TripRequestStatus) -> None:
    if target not in TRIP_REQUEST_TRANSITIONS[current]:
        raise ValueError(f"invalid TripRequest status transition: {current.value} -> {target.value}")


def validate_proposal_transition(current: ProposalStatus, target: ProposalStatus) -> None:
    if target not in PROPOSAL_TRANSITIONS[current]:
        raise ValueError(f"invalid Proposal status transition: {current.value} -> {target.value}")
