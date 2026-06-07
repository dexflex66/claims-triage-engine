"""Review queue repository."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ReviewAction, ReviewQueue


def enqueue(session: Session, case_id: str, packet: Dict[str, Any], status: str = "pending") -> ReviewQueue:
    row = ReviewQueue(case_id=case_id, packet=packet, status=status)
    session.add(row)
    return row


def list_pending(session: Session) -> List[ReviewQueue]:
    stmt = select(ReviewQueue).where(ReviewQueue.status == "pending").order_by(ReviewQueue.id.asc())
    return list(session.execute(stmt).scalars().all())


def set_status(session: Session, case_id: str, status: str) -> int:
    rows = session.execute(select(ReviewQueue).where(ReviewQueue.case_id == case_id).order_by(ReviewQueue.id.desc())).scalars().all()
    if not rows:
        return 0
    rows[0].status = status
    return 1


def add_action(session: Session, case_id: str, reviewer_id: str, action: str, note: str, timestamp_utc: str) -> ReviewAction:
    row = ReviewAction(
        case_id=case_id,
        reviewer_id=reviewer_id,
        action=action,
        note=note,
        timestamp_utc=timestamp_utc,
    )
    session.add(row)
    return row


def list_actions(session: Session, case_id: str) -> List[ReviewAction]:
    stmt = select(ReviewAction).where(ReviewAction.case_id == case_id).order_by(ReviewAction.id.asc())
    return list(session.execute(stmt).scalars().all())
