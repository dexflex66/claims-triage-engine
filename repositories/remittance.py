"""Remittance/adjudication repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Remittance, Submission
from local_claims_core import ParsedRemittance


def upsert_remittance(session: Session, parsed: ParsedRemittance) -> Remittance:
    row = session.execute(select(Remittance).where(Remittance.remittance_id == parsed.remittance_id)).scalar_one_or_none()
    if row is None:
        row = Remittance(remittance_id=parsed.remittance_id)
        session.add(row)

    row.case_id = parsed.case_id
    row.submission_id = parsed.submission_id
    row.external_ref = parsed.external_ref
    row.adjudication_status = parsed.adjudication_status
    row.paid_amount = parsed.paid_amount
    row.allowed_amount = parsed.allowed_amount
    row.denial_codes = parsed.denial_codes
    row.payer_claim_id = parsed.payer_claim_id
    row.source_format = parsed.source_format
    row.raw_payload = parsed.raw_payload
    row.timestamp_utc = parsed.timestamp_utc
    return row


def find_submission_for_remittance(session: Session, parsed: ParsedRemittance) -> Optional[Submission]:
    if parsed.submission_id:
        row = session.execute(select(Submission).where(Submission.submission_id == parsed.submission_id)).scalar_one_or_none()
        if row is not None:
            return row
    if parsed.external_ref:
        row = session.execute(select(Submission).where(Submission.external_ref == parsed.external_ref)).scalar_one_or_none()
        if row is not None:
            return row
    if parsed.case_id:
        stmt = (
            select(Submission)
            .where(Submission.case_id == parsed.case_id)
            .order_by(Submission.id.desc())
            .limit(1)
        )
        row = session.execute(stmt).scalars().first()
        if row is not None:
            return row
    return None


def list_remittances_by_case(session: Session, case_id: str) -> List[Remittance]:
    stmt = select(Remittance).where(Remittance.case_id == case_id).order_by(Remittance.id.desc())
    return list(session.execute(stmt).scalars().all())
