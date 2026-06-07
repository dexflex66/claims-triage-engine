"""Audit event schema and writer for HIPAA-ready audit trail.

Transition mode: persists to Postgres when available and mirrors to JSONL for
backward compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_AUDIT_DIR = Path(__file__).resolve().parent.parent / "data" / "audit"
_AUDIT_LOG_PATH = _AUDIT_DIR / "audit_events.jsonl"


def _ensure_audit_dir() -> None:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_audit_event(
    event_type: str,
    actor_id: str,
    resource_type: str,
    resource_id: str,
    outcome: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    timestamp_utc: Optional[str] = None,
    trace_id: str = "",
) -> Dict[str, Any]:
    """Append one audit event."""
    rec = {
        "event_type": event_type,
        "actor_id": actor_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "details": details or {},
        "timestamp_utc": timestamp_utc or _timestamp(),
        "trace_id": trace_id,
    }

    wrote_db = False
    try:
        from db.session import session_scope
        from repositories import audit as audit_repo

        with session_scope() as session:
            audit_repo.write_event(
                session,
                event_type=event_type,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                details=details or {},
                timestamp_utc=rec["timestamp_utc"],
                trace_id=trace_id,
            )
            wrote_db = True
    except Exception:
        wrote_db = False

    # Compatibility mirror for one transition release.
    _ensure_audit_dir()
    with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**rec, "db_written": wrote_db}, ensure_ascii=True) + "\n")

    return rec


# Event types for consistency
EVENT_ACCESS = "access"
EVENT_DECISION = "decision"
EVENT_APPROVE_TO_SEND = "approve_to_send"
EVENT_SUBMISSION = "submission"
EVENT_OUTCOME = "outcome"
EVENT_RETENTION_DELETE = "retention_delete"
