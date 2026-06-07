"""Pydantic request/response models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    field: str
    value: Any
    provenance: str
    page: Optional[int] = None
    line: Optional[int] = None


class CompileCaseRequest(BaseModel):
    case_id: str
    country: str
    payer_id: str
    fields: Dict[str, Any]
    evidence: List[EvidenceItem]


class CompileCaseResponse(BaseModel):
    case_id: str
    decision_kind: str
    decision_code: str
    reasons: List[str]
    trace_id: str
    compile_result: Dict[str, Any]


class ReviewActionRequest(BaseModel):
    reviewer_note: str = ""
    timestamp_utc: str = ""


class SubmitCaseRequest(BaseModel):
    submission_channel: str
    idempotency_key: str
    proof_artifact_ref: Optional[str] = None
    handoff_notes: str = ""
    timestamp_utc: str = ""


class SubmitCaseResponse(BaseModel):
    case_id: str
    submission_id: str
    external_ref: str
    status: str
    submitted_at: str


class StatusResponse(BaseModel):
    case_id: str
    submission_id: str
    external_ref: str
    status: str
    raw_status: Dict[str, Any]


class OutcomeRequest(BaseModel):
    outcome: str
    payer_id: Optional[str] = None
    procedure_code: Optional[str] = None
    diagnosis_code: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    turnaround_days: Optional[int] = None
    requested_addenda: List[str] = Field(default_factory=list)
    amount: Optional[float] = None
    timestamp_utc: str = ""


class RemittanceIngestRequest(BaseModel):
    source_format: str = "era_json"  # era_json | 835_text
    payload: Dict[str, Any]


class PaymentPostRequest(BaseModel):
    rail: str  # ach | virtual_card | erp
    idempotency_key: str
    amount: Optional[float] = None
    currency: str = "USD"
    beneficiary: Dict[str, Any] = Field(default_factory=dict)
