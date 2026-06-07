"""Submission layer with DB-first persistence and compatibility fallback."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SUBMISSIONS_PATH = _DATA_DIR / "submissions.jsonl"
_RECONCILIATION_PATH = _DATA_DIR / "reconciliation.jsonl"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_submission(
    case_id: str,
    method: str,
    proof_artifact_ref: Optional[str] = None,
    handoff_notes: str = "",
    timestamp_utc: str = "",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Record that a case was submitted (manual-first compatibility path)."""
    _ensure_data_dir()
    ts = timestamp_utc or _now()
    idem = idempotency_key or f"idem_{uuid4().hex[:20]}"
    submission_id = f"sub_{uuid4().hex[:16]}"
    rec = {
        "case_id": case_id,
        "method": method,
        "proof_artifact_ref": proof_artifact_ref,
        "handoff_notes": handoff_notes,
        "timestamp_utc": ts,
        "status": "submitted",
        "retry_count": 0,
        "idempotency_key": idem,
        "submission_id": submission_id,
    }

    wrote_db = False
    try:
        from db.session import session_scope
        from repositories import submissions as sub_repo

        with session_scope() as session:
            sub = sub_repo.create_or_get_idempotent(
                session,
                submission_id=submission_id,
                case_id=case_id,
                method=method,
                submission_channel=method,
                idempotency_key=idem,
                external_ref="",
                proof_artifact_ref=proof_artifact_ref or "",
                handoff_notes=handoff_notes,
                submitted_at=ts,
                status="submitted",
            )
            sub_repo.append_status(
                session,
                case_id=case_id,
                submission_id=sub.submission_id,
                external_ref=sub.external_ref,
                status=sub.status,
                raw_payload={"source": "record_submission"},
                timestamp_utc=ts,
            )
            rec["submission_id"] = sub.submission_id
            wrote_db = True
    except Exception:
        wrote_db = False

    with _SUBMISSIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**rec, "db_written": wrote_db}, ensure_ascii=True) + "\n")
    return rec


def record_retry(case_id: str, reason: str, timestamp_utc: str) -> None:
    _ensure_data_dir()
    rec = {
        "case_id": case_id,
        "event": "retry",
        "reason": reason,
        "timestamp_utc": timestamp_utc,
    }
    with _SUBMISSIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def record_timeout(case_id: str, timeout_after_days: int, timestamp_utc: str) -> None:
    _ensure_data_dir()
    rec = {
        "case_id": case_id,
        "event": "timeout",
        "timeout_after_days": timeout_after_days,
        "timestamp_utc": timestamp_utc,
    }

    try:
        from db.session import session_scope
        from repositories import submissions as sub_repo

        with session_scope() as session:
            sub = sub_repo.get_latest_submission(session, case_id)
            if sub is not None:
                sub_repo.append_status(
                    session,
                    case_id=case_id,
                    submission_id=sub.submission_id,
                    external_ref=sub.external_ref,
                    status="timeout",
                    raw_payload={"timeout_after_days": timeout_after_days},
                    timestamp_utc=timestamp_utc,
                )
    except Exception:
        pass

    with _SUBMISSIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def record_received(
    case_id: str,
    payer_reference_id: Optional[str] = None,
    received_status: str = "received",
    timestamp_utc: str = "",
) -> Dict[str, Any]:
    _ensure_data_dir()
    rec = {
        "case_id": case_id,
        "payer_reference_id": payer_reference_id,
        "received_status": received_status,
        "timestamp_utc": timestamp_utc,
        "event": "received",
    }

    try:
        from db.session import session_scope
        from repositories import submissions as sub_repo

        with session_scope() as session:
            sub_repo.add_reconciliation_event(
                session,
                case_id=case_id,
                event="received",
                payload={"payer_reference_id": payer_reference_id, "received_status": received_status},
                timestamp_utc=timestamp_utc,
            )
    except Exception:
        pass

    with _RECONCILIATION_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")
    return rec


def get_submission_events(case_id: str) -> List[Dict[str, Any]]:
    out = []
    if _SUBMISSIONS_PATH.exists():
        with _SUBMISSIONS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("case_id") == case_id:
                    out.append(rec)
    return out


def get_retry_count(case_id: str) -> int:
    return sum(1 for r in get_submission_events(case_id) if r.get("event") == "retry")


def list_sent_not_received() -> List[str]:
    try:
        from db.session import session_scope
        from repositories import submissions as sub_repo

        with session_scope() as session:
            ids = sub_repo.list_sent_not_received(session)
            if ids:
                return ids
    except Exception:
        pass

    sent = set()
    received = set()
    if _SUBMISSIONS_PATH.exists():
        with _SUBMISSIONS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("case_id") and rec.get("status") == "submitted":
                    sent.add(rec["case_id"])
    if _RECONCILIATION_PATH.exists():
        with _RECONCILIATION_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("case_id") and rec.get("event") == "received":
                    received.add(rec["case_id"])
    return list(sent - received)
