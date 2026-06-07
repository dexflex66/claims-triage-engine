"""Outcome and KPI repositories."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import KpiSnapshot, Outcome


def record_outcome(
    session: Session,
    *,
    case_id: str,
    outcome: str,
    payer_id: Optional[str],
    procedure_code: Optional[str],
    diagnosis_code: Optional[str],
    reason_codes: List[str],
    turnaround_days: Optional[int],
    requested_addenda: List[str],
    amount: Optional[float],
    timestamp_utc: str,
) -> Outcome:
    row = Outcome(
        case_id=case_id,
        outcome=outcome,
        payer_id=payer_id or "",
        procedure_code=procedure_code or "",
        diagnosis_code=diagnosis_code or "",
        reason_codes=reason_codes,
        turnaround_days=turnaround_days,
        requested_addenda=requested_addenda,
        amount=amount,
        timestamp_utc=timestamp_utc,
    )
    session.add(row)
    return row


def get_outcomes_by_payer_code(session: Session, payer_id: str, procedure_code: str) -> List[Outcome]:
    stmt = select(Outcome).where(Outcome.payer_id == payer_id, Outcome.procedure_code == procedure_code)
    return list(session.execute(stmt).scalars().all())


def compute_kpis(session: Session) -> Dict[str, Any]:
    outcomes = list(session.execute(select(Outcome)).scalars().all())
    if not outcomes:
        return {
            "denial_rate": 0.0,
            "resubmission_rate": 0.0,
            "days_to_approval": None,
            "recovered_revenue": 0.0,
            "count": 0,
        }

    total = len(outcomes)
    denied = sum(1 for o in outcomes if o.outcome == "denied")
    approved = [o for o in outcomes if o.outcome == "approved"]
    avg_days = None
    if approved:
        vals = [o.turnaround_days for o in approved if o.turnaround_days is not None]
        if vals:
            avg_days = sum(vals) / len(vals)

    recovered = sum(float(o.amount or 0.0) for o in approved)

    # Placeholder resubmission heuristic: cases with addenda are assumed rework.
    rework = sum(1 for o in outcomes if (o.requested_addenda or []))

    return {
        "denial_rate": denied / total,
        "resubmission_rate": rework / total,
        "days_to_approval": avg_days,
        "recovered_revenue": recovered,
        "count": total,
    }


def save_kpi_snapshot(session: Session, payload: Dict[str, Any], scope: str = "global") -> KpiSnapshot:
    row = KpiSnapshot(scope=scope, payload=payload)
    session.add(row)
    return row
