"""Human review queue with DB-first persistence and JSONL fallback."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_QUEUE_PATH = _DATA_DIR / "review_queue.jsonl"
_APPROVALS_PATH = _DATA_DIR / "approvals.jsonl"
_STATUS_PATH = _DATA_DIR / "review_status.jsonl"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def enqueue_for_review(case_id: str, packet: Dict[str, Any], created_at: str) -> None:
    """Append ABSTAIN case to review queue."""
    _ensure_data_dir()

    wrote_db = False
    try:
        from db.session import session_scope
        from repositories import review as review_repo

        with session_scope() as session:
            review_repo.enqueue(session, case_id=case_id, packet=packet, status="pending")
            wrote_db = True
    except Exception:
        wrote_db = False

    item = {
        "case_id": case_id,
        "decision_kind": packet.get("decision_kind", "ABSTAIN"),
        "packet": packet,
        "created_at": created_at,
        "status": "pending",
        "db_written": wrote_db,
    }
    with _QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=True) + "\n")


def list_pending_review() -> List[Dict[str, Any]]:
    """Return all pending review items."""
    try:
        from db.session import session_scope
        from repositories import review as review_repo

        with session_scope() as session:
            rows = review_repo.list_pending(session)
            if rows:
                return [
                    {
                        "case_id": r.case_id,
                        "decision_kind": r.packet.get("decision_kind", "ABSTAIN") if isinstance(r.packet, dict) else "ABSTAIN",
                        "packet": r.packet,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                        "status": r.status,
                    }
                    for r in rows
                ]
    except Exception:
        pass

    if not _QUEUE_PATH.exists():
        return []
    out = []
    with _QUEUE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("status") == "pending":
                out.append(rec)
    return out


def approve_to_send(case_id: str, reviewer_id: str, note: str, timestamp_utc: str) -> Dict[str, Any]:
    """Record immutable approval and mark queue item approved."""
    _ensure_data_dir()
    approval = {
        "case_id": case_id,
        "reviewer_id": reviewer_id,
        "note": note,
        "timestamp_utc": timestamp_utc,
        "action": "approve_to_send",
    }

    try:
        from db.session import session_scope
        from repositories import review as review_repo

        with session_scope() as session:
            review_repo.add_action(session, case_id, reviewer_id, "approve_to_send", note, timestamp_utc)
            review_repo.set_status(session, case_id, "approved")
    except Exception:
        pass

    with _APPROVALS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(approval, ensure_ascii=True) + "\n")
    _append_status_update(case_id, "approved", reviewer_id, note, timestamp_utc)
    return approval


def reject_review(case_id: str, reviewer_id: str, note: str, timestamp_utc: str) -> Dict[str, Any]:
    """Record rejection and mark queue item rejected."""
    _ensure_data_dir()
    rec = {
        "case_id": case_id,
        "reviewer_id": reviewer_id,
        "note": note,
        "timestamp_utc": timestamp_utc,
        "action": "reject",
    }

    try:
        from db.session import session_scope
        from repositories import review as review_repo

        with session_scope() as session:
            review_repo.add_action(session, case_id, reviewer_id, "reject", note, timestamp_utc)
            review_repo.set_status(session, case_id, "rejected")
    except Exception:
        pass

    with _APPROVALS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")
    _append_status_update(case_id, "rejected", reviewer_id, note, timestamp_utc)
    return rec


def _append_status_update(case_id: str, status: str, reviewer_id: str, note: str, timestamp_utc: str) -> None:
    rec = {
        "case_id": case_id,
        "status": status,
        "reviewer_id": reviewer_id,
        "note": note,
        "timestamp_utc": timestamp_utc,
    }
    _ensure_data_dir()
    with _STATUS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def get_pending_case_ids() -> set:
    decided = set()
    if _STATUS_PATH.exists():
        with _STATUS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                decided.add(rec.get("case_id"))
    return decided


def list_pending_review_excluding_decided() -> List[Dict[str, Any]]:
    decided = get_pending_case_ids()
    return [r for r in list_pending_review() if r.get("case_id") not in decided]
