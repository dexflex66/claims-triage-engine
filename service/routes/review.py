from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from repositories import audit as audit_repo
from repositories import cases as case_repo
from repositories import review as review_repo
from service.deps import get_db, get_trace_id
from service.schemas import ReviewActionRequest
from service.security.oidc import AuthContext, require_roles

router = APIRouter(prefix="/v1/cases", tags=["review"])


@router.post("/{case_id}/review/approve")
def approve_case(
    case_id: str,
    payload: ReviewActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("reviewer", "admin")),
):
    updated = review_repo.set_status(db, case_id, "approved")
    if updated == 0:
        latest = case_repo.get_latest_compile_result(db, case_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="Case not found")
        review_repo.enqueue(db, case_id, latest.result.get("approval_packet", {}), status="approved")

    review_repo.add_action(db, case_id, auth.subject, "approve_to_send", payload.reviewer_note, payload.timestamp_utc)
    audit_repo.write_event(
        db,
        event_type="approve_to_send",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome="approved",
        details={"note": payload.reviewer_note},
        timestamp_utc=payload.timestamp_utc,
        trace_id=get_trace_id(request),
    )
    return {"case_id": case_id, "status": "approved"}


@router.post("/{case_id}/review/reject")
def reject_case(
    case_id: str,
    payload: ReviewActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("reviewer", "admin")),
):
    updated = review_repo.set_status(db, case_id, "rejected")
    if updated == 0:
        latest = case_repo.get_latest_compile_result(db, case_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="Case not found")
        review_repo.enqueue(db, case_id, latest.result.get("approval_packet", {}), status="rejected")

    review_repo.add_action(db, case_id, auth.subject, "reject", payload.reviewer_note, payload.timestamp_utc)
    audit_repo.write_event(
        db,
        event_type="review_reject",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome="rejected",
        details={"note": payload.reviewer_note},
        timestamp_utc=payload.timestamp_utc,
        trace_id=get_trace_id(request),
    )
    return {"case_id": case_id, "status": "rejected"}
