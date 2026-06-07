from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from connectors import get_connector
from repositories import audit as audit_repo
from repositories import cases as case_repo
from repositories import review as review_repo
from repositories import submissions as sub_repo
from service.deps import get_db, get_trace_id
from service.schemas import StatusResponse, SubmitCaseRequest, SubmitCaseResponse
from service.security.oidc import AuthContext, require_roles


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


case_router = APIRouter(prefix="/v1/cases", tags=["submission"])
queue_router = APIRouter(prefix="/v1/queues", tags=["review_queue"])
recon_router = APIRouter(prefix="/v1/reconciliation", tags=["reconciliation"])


@case_router.post("/{case_id}/submit", response_model=SubmitCaseResponse)
def submit_case(
    case_id: str,
    payload: SubmitCaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("ops_submitter", "admin", "reviewer")),
):
    latest = case_repo.get_latest_compile_result(db, case_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_row = case_repo.get_case(db, case_id)
    if case_row is None:
        raise HTTPException(status_code=404, detail="Case fields missing")

    connector = get_connector(case_row.country, case_row.payer_id)
    packet = latest.result.get("approval_packet", {})
    ack = connector.submit(packet=packet, idempotency_key=payload.idempotency_key)

    submitted_at = payload.timestamp_utc or _now()
    sub = sub_repo.create_or_get_idempotent(
        db,
        submission_id=ack.submission_id,
        case_id=case_id,
        method=payload.submission_channel,
        submission_channel=payload.submission_channel,
        idempotency_key=payload.idempotency_key,
        external_ref=ack.external_ref,
        proof_artifact_ref=payload.proof_artifact_ref or "",
        handoff_notes=payload.handoff_notes,
        submitted_at=submitted_at,
        status=ack.status,
    )
    sub_repo.append_status(
        db,
        case_id=case_id,
        submission_id=sub.submission_id,
        external_ref=sub.external_ref,
        status=sub.status,
        raw_payload=ack.raw_payload,
        timestamp_utc=submitted_at,
    )
    audit_repo.write_event(
        db,
        event_type="submission",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome=sub.status,
        details={"external_ref": sub.external_ref, "channel": payload.submission_channel},
        timestamp_utc=submitted_at,
        trace_id=get_trace_id(request),
    )

    return SubmitCaseResponse(
        case_id=case_id,
        submission_id=sub.submission_id,
        external_ref=sub.external_ref,
        status=sub.status,
        submitted_at=submitted_at,
    )


@case_router.get("/{case_id}/status", response_model=StatusResponse)
def get_status(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("viewer", "reviewer", "admin", "ops_submitter")),
):
    sub = sub_repo.get_latest_submission(db, case_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No submission found")

    case_row = case_repo.get_case(db, case_id)
    if case_row is None:
        raise HTTPException(status_code=404, detail="Case fields missing")

    connector = get_connector(case_row.country, case_row.payer_id)
    status = connector.poll_status(sub.external_ref)
    now = _now()
    raw_payload = dict(status.raw_payload or {})
    if status.status in {"approved", "denied"}:
        try:
            receipt = connector.fetch_receipt(sub.external_ref)
            raw_payload["receipt_artifact_ref"] = receipt.artifact_ref
            raw_payload["receipt_payload"] = receipt.raw_payload
        except Exception as exc:
            raw_payload["receipt_error"] = str(exc)
    sub_repo.append_status(
        db,
        case_id=case_id,
        submission_id=sub.submission_id,
        external_ref=sub.external_ref,
        status=status.status,
        raw_payload=raw_payload,
        timestamp_utc=now,
    )
    audit_repo.write_event(
        db,
        event_type="status_poll",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome=status.status,
        details={"external_ref": sub.external_ref},
        timestamp_utc=now,
        trace_id=get_trace_id(request),
    )

    return StatusResponse(
        case_id=case_id,
        submission_id=sub.submission_id,
        external_ref=sub.external_ref,
        status=status.status,
        raw_status=raw_payload,
    )


@queue_router.get("/review")
def list_review_queue(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("viewer", "reviewer", "admin")),
):
    items = review_repo.list_pending(db)
    return [
        {
            "case_id": i.case_id,
            "status": i.status,
            "packet": i.packet,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]


@recon_router.get("/sent-not-received")
def sent_not_received(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "ops_submitter", "reviewer")),
):
    case_ids = sub_repo.list_sent_not_received(db)
    now = _now()
    for cid in case_ids:
        sub_repo.add_reconciliation_event(
            db,
            case_id=cid,
            event="sent_not_received",
            payload={"detected_at": now},
            timestamp_utc=now,
        )
    audit_repo.write_event(
        db,
        event_type="reconciliation_scan",
        actor_id=auth.subject,
        resource_type="system",
        resource_id="reconciliation",
        outcome="ok",
        details={"unreconciled_count": len(case_ids)},
        timestamp_utc=now,
        trace_id=get_trace_id(request),
    )
    return {"case_ids": case_ids, "count": len(case_ids)}
