"""Payment posting repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import PaymentPosting, Remittance


def create_or_get_idempotent(
    session: Session,
    *,
    payment_post_id: str,
    case_id: str,
    remittance_id: str,
    rail: str,
    amount: float,
    currency: str,
    idempotency_key: str,
    external_ref: str,
    status: str,
    raw_payload: dict,
    posted_at: str,
) -> PaymentPosting:
    existing = session.execute(
        select(PaymentPosting).where(
            PaymentPosting.case_id == case_id,
            PaymentPosting.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    row = PaymentPosting(
        payment_post_id=payment_post_id,
        case_id=case_id,
        remittance_id=remittance_id,
        rail=rail,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        external_ref=external_ref,
        status=status,
        raw_payload=raw_payload,
        posted_at=posted_at,
    )
    session.add(row)
    return row


def list_by_case(session: Session, case_id: str) -> List[PaymentPosting]:
    stmt = select(PaymentPosting).where(PaymentPosting.case_id == case_id).order_by(PaymentPosting.id.desc())
    return list(session.execute(stmt).scalars().all())


def latest_approved_remittance(session: Session, case_id: str) -> Optional[Remittance]:
    stmt = (
        select(Remittance)
        .where(Remittance.case_id == case_id, Remittance.adjudication_status == "approved")
        .order_by(Remittance.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()
