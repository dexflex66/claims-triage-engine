"""SQLAlchemy models for production persistence."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base."""


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)
    payer_id: Mapped[str] = mapped_column(String(64), index=True)
    fields: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CaseEvidence(Base):
    __tablename__ = "case_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompileResult(Base):
    __tablename__ = "compile_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    decision_kind: Mapped[str] = mapped_column(String(32), index=True)
    decision_code: Mapped[str] = mapped_column(String(64), default="REVIEW")
    result: Mapped[dict] = mapped_column(JSON)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    packet: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_submission_case_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    method: Mapped[str] = mapped_column(String(64))
    submission_channel: Mapped[str] = mapped_column(String(64), default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    external_ref: Mapped[str] = mapped_column(String(256), default="")
    proof_artifact_ref: Mapped[str] = mapped_column(String(512), default="")
    handoff_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[str] = mapped_column(String(64), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")


class SubmissionStatusHistory(Base):
    __tablename__ = "submission_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    submission_id: Mapped[str] = mapped_column(String(128), index=True)
    external_ref: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default={})
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class ReconciliationEvent(Base):
    __tablename__ = "reconciliation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default={})
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    payer_id: Mapped[str] = mapped_column(String(64), default="")
    procedure_code: Mapped[str] = mapped_column(String(64), default="")
    diagnosis_code: Mapped[str] = mapped_column(String(64), default="")
    reason_codes: Mapped[list] = mapped_column(JSON, default=[])
    turnaround_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_addenda: Mapped[list] = mapped_column(JSON, default=[])
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class Remittance(Base):
    __tablename__ = "remittances"
    __table_args__ = (UniqueConstraint("remittance_id", name="uq_remittance_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    remittance_id: Mapped[str] = mapped_column(String(128), index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    submission_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    external_ref: Mapped[str] = mapped_column(String(256), index=True, default="")
    adjudication_status: Mapped[str] = mapped_column(String(32), index=True, default="processing")
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    allowed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    denial_codes: Mapped[list] = mapped_column(JSON, default=[])
    payer_claim_id: Mapped[str] = mapped_column(String(128), default="")
    source_format: Mapped[str] = mapped_column(String(32), default="era_json")
    raw_payload: Mapped[dict] = mapped_column(JSON, default={})
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class PaymentPosting(Base):
    __tablename__ = "payment_postings"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_payment_case_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_post_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    remittance_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    rail: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    external_ref: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="posted")
    raw_payload: Mapped[dict] = mapped_column(JSON, default={})
    posted_at: Mapped[str] = mapped_column(String(64), default="")


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payer_id: Mapped[str] = mapped_column(String(64), index=True)
    procedure_code: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    outcome: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default={})
    trace_id: Mapped[str] = mapped_column(String(64), default="")
    timestamp_utc: Mapped[str] = mapped_column(String(64), default="")


class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(64), index=True, default="global")
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
