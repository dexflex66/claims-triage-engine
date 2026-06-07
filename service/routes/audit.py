from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from repositories import audit as audit_repo
from service.deps import get_db
from service.security.oidc import AuthContext, require_roles

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/events")
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    event_type: str | None = None,
    resource_id: str | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "reviewer")),
):
    rows = audit_repo.list_events(db, limit=limit, event_type=event_type, resource_id=resource_id)
    return [
        {
            "event_type": r.event_type,
            "actor_id": r.actor_id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "outcome": r.outcome,
            "details": r.details,
            "timestamp_utc": r.timestamp_utc,
            "trace_id": r.trace_id,
        }
        for r in rows
    ]
