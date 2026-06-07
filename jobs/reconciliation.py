"""Background reconciliation job."""
from __future__ import annotations

from datetime import datetime, timezone

from db.session import session_scope
from repositories import submissions as sub_repo


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_reconciliation_scan() -> dict:
    with session_scope() as session:
        case_ids = sub_repo.list_sent_not_received(session)
        ts = _now()
        for cid in case_ids:
            sub_repo.add_reconciliation_event(
                session,
                case_id=cid,
                event="sent_not_received",
                payload={"detected_at": ts},
                timestamp_utc=ts,
            )
        return {"count": len(case_ids), "case_ids": case_ids}
