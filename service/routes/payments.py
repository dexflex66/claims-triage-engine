from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from payments.adapters import get_payment_adapter
from repositories import audit as audit_repo
from repositories import payments as payment_repo
from service.deps import get_db, get_trace_id
from service.schemas import PaymentPostRequest
from service.security.oidc import AuthContext, require_roles


router = APIRouter(prefix="/v1/cases", tags=["payments"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/{case_id}/payment/post")
def post_payment(
    case_id: str,
    payload: PaymentPostRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("ops_submitter", "admin")),
):
    rem = payment_repo.latest_approved_remittance(db, case_id)
    if rem is None:
        raise HTTPException(status_code=409, detail="approved_remittance_required")

    amount = float(payload.amount if payload.amount is not None else rem.paid_amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="invalid_payment_amount")

    adapter = get_payment_adapter(payload.rail)
    posting_payload = {
        "case_id": case_id,
        "remittance_id": rem.remittance_id,
        "amount": amount,
        "currency": payload.currency,
        "beneficiary": payload.beneficiary,
        "payer_claim_id": rem.payer_claim_id,
    }
    result = adapter.post_payment(posting_payload, idempotency_key=payload.idempotency_key)

    posted_at = _now()
    row = payment_repo.create_or_get_idempotent(
        db,
        payment_post_id=result.payment_post_id,
        case_id=case_id,
        remittance_id=rem.remittance_id,
        rail=result.rail,
        amount=amount,
        currency=payload.currency,
        idempotency_key=payload.idempotency_key,
        external_ref=result.external_ref,
        status=result.status,
        raw_payload=result.raw_payload,
        posted_at=posted_at,
    )

    audit_repo.write_event(
        db,
        event_type="payment_post",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome=row.status,
        details={"rail": row.rail, "payment_post_id": row.payment_post_id, "amount": row.amount},
        timestamp_utc=posted_at,
        trace_id=get_trace_id(request),
    )

    return {
        "case_id": row.case_id,
        "payment_post_id": row.payment_post_id,
        "rail": row.rail,
        "status": row.status,
        "amount": row.amount,
        "currency": row.currency,
        "external_ref": row.external_ref,
    }


@router.get("/{case_id}/payment/posts")
def list_payment_posts(
    case_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("viewer", "reviewer", "admin", "ops_submitter")),
):
    rows = payment_repo.list_by_case(db, case_id)
    return [
        {
            "payment_post_id": r.payment_post_id,
            "case_id": r.case_id,
            "remittance_id": r.remittance_id,
            "rail": r.rail,
            "amount": r.amount,
            "currency": r.currency,
            "status": r.status,
            "external_ref": r.external_ref,
            "posted_at": r.posted_at,
        }
        for r in rows
    ]
