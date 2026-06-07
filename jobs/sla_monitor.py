"""SLA monitoring for submission pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db.models import Submission
from db.session import session_scope


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def compute_sla_report(unresolved_hours_sla: int = 24) -> dict:
    with session_scope() as session:
        rows = list(session.execute(select(Submission)).scalars().all())

    total = len(rows)
    accepted = sum(1 for r in rows if r.status in {"submitted", "acknowledged", "processing", "approved", "denied"})
    unresolved = [r for r in rows if r.status in {"submitted", "acknowledged", "processing"}]

    cutoff = _now() - timedelta(hours=unresolved_hours_sla)
    old_unresolved = 0
    for r in unresolved:
        dt = _parse_iso(r.submitted_at)
        if dt is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt is not None and dt < cutoff:
            old_unresolved += 1

    success_rate = (accepted / total) if total else 1.0
    unresolved_ratio = (old_unresolved / total) if total else 0.0

    return {
        "total_submissions": total,
        "accepted_or_progressing": accepted,
        "success_rate": success_rate,
        "unresolved_older_than_sla": old_unresolved,
        "unresolved_ratio": unresolved_ratio,
        "sla_hours": unresolved_hours_sla,
    }
