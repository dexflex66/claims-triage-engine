"""Submission status polling job."""
from __future__ import annotations

from datetime import datetime, timezone

from connectors import get_connector
from db.session import session_scope
from repositories import cases as case_repo
from repositories import submissions as sub_repo


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def poll_case_status(case_id: str) -> dict:
    with session_scope() as session:
        sub = sub_repo.get_latest_submission(session, case_id)
        if sub is None:
            return {"case_id": case_id, "status": "missing_submission"}

        case_row = case_repo.get_case(session, case_id)
        if case_row is None:
            return {"case_id": case_id, "status": "missing_case"}

        connector = get_connector(case_row.country, case_row.payer_id)
        st = connector.poll_status(sub.external_ref)
        sub_repo.append_status(
            session,
            case_id=case_id,
            submission_id=sub.submission_id,
            external_ref=sub.external_ref,
            status=st.status,
            raw_payload=st.raw_payload,
            timestamp_utc=_now(),
        )
        return {"case_id": case_id, "status": st.status}
