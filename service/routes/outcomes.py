from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from repositories import audit as audit_repo
from repositories import outcomes as outcome_repo
from service.deps import get_db, get_trace_id
from service.schemas import OutcomeRequest
from service.security.oidc import AuthContext, require_roles


router = APIRouter(prefix="/v1/cases", tags=["outcomes"])
metrics_router = APIRouter(prefix="/v1/metrics", tags=["metrics"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/{case_id}/outcome")
def post_outcome(
    case_id: str,
    payload: OutcomeRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("reviewer", "admin", "ops_submitter")),
):
    ts = payload.timestamp_utc or _now()
    rec = outcome_repo.record_outcome(
        db,
        case_id=case_id,
        outcome=payload.outcome,
        payer_id=payload.payer_id,
        procedure_code=payload.procedure_code,
        diagnosis_code=payload.diagnosis_code,
        reason_codes=payload.reason_codes,
        turnaround_days=payload.turnaround_days,
        requested_addenda=payload.requested_addenda,
        amount=payload.amount,
        timestamp_utc=ts,
    )
    audit_repo.write_event(
        db,
        event_type="outcome",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=case_id,
        outcome=payload.outcome,
        details={"reason_codes": payload.reason_codes},
        timestamp_utc=ts,
        trace_id=get_trace_id(request),
    )
    return {
        "case_id": rec.case_id,
        "outcome": rec.outcome,
        "timestamp_utc": rec.timestamp_utc,
    }


@metrics_router.get("/kpis")
def get_kpis(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("viewer", "reviewer", "admin")),
):
    payload = outcome_repo.compute_kpis(db)
    snap = outcome_repo.save_kpi_snapshot(db, payload)
    audit_repo.write_event(
        db,
        event_type="kpi_snapshot",
        actor_id=auth.subject,
        resource_type="system",
        resource_id="kpis",
        outcome="ok",
        details={"snapshot_id": snap.id},
        timestamp_utc=_now(),
        trace_id=get_trace_id(request),
    )
    return payload
