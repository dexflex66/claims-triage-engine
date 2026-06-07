"""Audit repository."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AuditEvent


def write_event(
    session: Session,
    *,
    event_type: str,
    actor_id: str,
    resource_type: str,
    resource_id: str,
    outcome: Optional[str],
    details: Dict[str, Any],
    timestamp_utc: str,
    trace_id: str = "",
) -> AuditEvent:
    row = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome or "",
        details=details,
        timestamp_utc=timestamp_utc,
        trace_id=trace_id,
    )
    session.add(row)
    return row


def list_events(
    session: Session,
    *,
    limit: int = 100,
    event_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> List[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if resource_id:
        stmt = stmt.where(AuditEvent.resource_id == resource_id)
    return list(session.execute(stmt).scalars().all())
