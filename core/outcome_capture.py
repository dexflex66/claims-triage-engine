"""Outcome capture with DB-first persistence and JSONL fallback."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_OUTCOMES_PATH = _DATA_DIR / "outcomes.jsonl"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def record_outcome(
    case_id: str,
    outcome: str,
    payer_id: Optional[str] = None,
    procedure_code: Optional[str] = None,
    diagnosis_code: Optional[str] = None,
    reason_codes: Optional[List[str]] = None,
    turnaround_days: Optional[int] = None,
    requested_addenda: Optional[List[str]] = None,
    timestamp_utc: str = "",
    amount: Optional[float] = None,
) -> Dict[str, Any]:
    """Capture outcome for a case; used by playbook updater."""
    _ensure_data_dir()
    rec = {
        "case_id": case_id,
        "outcome": outcome,
        "payer_id": payer_id,
        "procedure_code": procedure_code,
        "diagnosis_code": diagnosis_code,
        "reason_codes": reason_codes or [],
        "turnaround_days": turnaround_days,
        "requested_addenda": requested_addenda or [],
        "timestamp_utc": timestamp_utc,
        "amount": amount,
    }

    wrote_db = False
    try:
        from db.session import session_scope
        from repositories import outcomes as outcome_repo

        with session_scope() as session:
            outcome_repo.record_outcome(
                session,
                case_id=case_id,
                outcome=outcome,
                payer_id=payer_id,
                procedure_code=procedure_code,
                diagnosis_code=diagnosis_code,
                reason_codes=reason_codes or [],
                turnaround_days=turnaround_days,
                requested_addenda=requested_addenda or [],
                amount=amount,
                timestamp_utc=timestamp_utc,
            )
            wrote_db = True
    except Exception:
        wrote_db = False

    with _OUTCOMES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**rec, "db_written": wrote_db}, ensure_ascii=True) + "\n")
    return rec


def get_outcomes_by_payer_code(payer_id: str, procedure_code: str) -> List[Dict[str, Any]]:
    """Fetch outcomes for playbook: payer + code."""
    try:
        from db.session import session_scope
        from repositories import outcomes as outcome_repo

        with session_scope() as session:
            rows = outcome_repo.get_outcomes_by_payer_code(session, payer_id, procedure_code)
            if rows:
                return [
                    {
                        "case_id": r.case_id,
                        "outcome": r.outcome,
                        "payer_id": r.payer_id,
                        "procedure_code": r.procedure_code,
                        "diagnosis_code": r.diagnosis_code,
                        "reason_codes": r.reason_codes,
                        "turnaround_days": r.turnaround_days,
                        "requested_addenda": r.requested_addenda,
                        "timestamp_utc": r.timestamp_utc,
                    }
                    for r in rows
                ]
    except Exception:
        pass

    out = []
    if not _OUTCOMES_PATH.exists():
        return out
    with _OUTCOMES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("payer_id") == payer_id and rec.get("procedure_code") == procedure_code:
                out.append(rec)
    return out
