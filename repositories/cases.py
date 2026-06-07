"""Repositories for case ingestion and compile results."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import Case, CaseEvidence, CompileResult


def upsert_case(session: Session, case_id: str, country: str, payer_id: str, fields: Dict[str, Any]) -> Case:
    row = session.execute(select(Case).where(Case.case_id == case_id)).scalar_one_or_none()
    if row is None:
        row = Case(case_id=case_id, country=country, payer_id=payer_id, fields=fields)
        session.add(row)
    else:
        row.country = country
        row.payer_id = payer_id
        row.fields = fields
    return row


def replace_case_evidence(session: Session, case_id: str, evidence: List[Dict[str, Any]]) -> None:
    session.execute(delete(CaseEvidence).where(CaseEvidence.case_id == case_id))
    for ev in evidence:
        session.add(CaseEvidence(case_id=case_id, evidence=ev))


def save_compile_result(
    session: Session,
    case_id: str,
    decision_kind: str,
    decision_code: str,
    result: Dict[str, Any],
    trace_id: str,
) -> CompileResult:
    row = CompileResult(
        case_id=case_id,
        decision_kind=decision_kind,
        decision_code=decision_code,
        result=result,
        trace_id=trace_id,
    )
    session.add(row)
    return row


def get_latest_compile_result(session: Session, case_id: str) -> Optional[CompileResult]:
    stmt = (
        select(CompileResult)
        .where(CompileResult.case_id == case_id)
        .order_by(CompileResult.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_case(session: Session, case_id: str) -> Optional[Case]:
    return session.execute(select(Case).where(Case.case_id == case_id)).scalar_one_or_none()
