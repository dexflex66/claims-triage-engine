"""Submission and reconciliation repositories."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import ReconciliationEvent, Submission, SubmissionStatusHistory


ALLOWED_STATUSES = {
    "queued",
    "submitted",
    "acknowledged",
    "processing",
    "approved",
    "denied",
    "failed",
    "timeout",
}


def create_or_get_idempotent(
    session: Session,
    *,
    submission_id: str,
    case_id: str,
    method: str,
    submission_channel: str,
    idempotency_key: str,
    external_ref: str,
    proof_artifact_ref: str,
    handoff_notes: str,
    submitted_at: str,
    status: str,
) -> Submission:
    existing = session.execute(
        select(Submission).where(
            Submission.case_id == case_id,
            Submission.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported status: {status}")

    row = Submission(
        submission_id=submission_id,
        case_id=case_id,
        method=method,
        submission_channel=submission_channel,
        idempotency_key=idempotency_key,
        external_ref=external_ref,
        proof_artifact_ref=proof_artifact_ref,
        handoff_notes=handoff_notes,
        status=status,
        submitted_at=submitted_at,
    )
    session.add(row)
    return row


def append_status(
    session: Session,
    *,
    case_id: str,
    submission_id: str,
    external_ref: str,
    status: str,
    raw_payload: Dict[str, Any],
    timestamp_utc: str,
) -> SubmissionStatusHistory:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    row = SubmissionStatusHistory(
        case_id=case_id,
        submission_id=submission_id,
        external_ref=external_ref,
        status=status,
        raw_payload=raw_payload,
        timestamp_utc=timestamp_utc,
    )
    session.add(row)

    sub = session.execute(select(Submission).where(Submission.submission_id == submission_id)).scalar_one_or_none()
    if sub is not None:
        sub.status = status
        sub.external_ref = external_ref or sub.external_ref
    return row


def list_sent_not_received(session: Session) -> List[str]:
    sent = set(
        session.execute(select(Submission.case_id).where(Submission.status.in_(["submitted", "acknowledged", "processing"]))).scalars().all()
    )
    received = set(
        session.execute(
            select(SubmissionStatusHistory.case_id).where(
                SubmissionStatusHistory.status.in_(["approved", "denied"])
            )
        ).scalars().all()
    )
    return sorted(sent - received)


def get_latest_submission(session: Session, case_id: str) -> Optional[Submission]:
    stmt = (
        select(Submission)
        .where(Submission.case_id == case_id)
        .order_by(Submission.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def add_reconciliation_event(session: Session, case_id: str, event: str, payload: Dict[str, Any], timestamp_utc: str) -> ReconciliationEvent:
    row = ReconciliationEvent(case_id=case_id, event=event, payload=payload, timestamp_utc=timestamp_utc)
    session.add(row)
    return row
