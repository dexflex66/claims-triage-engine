from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from local_claims_core import parse_835_text, parse_era_json
from repositories import audit as audit_repo
from repositories import outcomes as outcome_repo
from repositories import remittance as remittance_repo
from repositories import submissions as submission_repo
from service.deps import get_db, get_trace_id
from service.schemas import RemittanceIngestRequest
from service.security.oidc import AuthContext, require_roles


router = APIRouter(prefix="/v1/remittance", tags=["remittance"])
case_router = APIRouter(prefix="/v1/cases", tags=["remittance"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/ingest")
def ingest_remittance(
    payload: RemittanceIngestRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("ops_submitter", "admin", "reviewer")),
):
    try:
        if payload.source_format == "era_json":
            parsed = parse_era_json(payload.payload)
        elif payload.source_format == "835_text":
            parsed = parse_835_text(str(payload.payload.get("raw_text", "")))
        else:
            raise HTTPException(status_code=400, detail="unsupported_source_format")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid_remittance_payload:{exc}") from exc

    sub = remittance_repo.find_submission_for_remittance(db, parsed)
    if sub is not None:
        if not parsed.case_id:
            parsed.case_id = sub.case_id
        if not parsed.submission_id:
            parsed.submission_id = sub.submission_id
        if not parsed.external_ref:
            parsed.external_ref = sub.external_ref

        submission_repo.append_status(
            db,
            case_id=sub.case_id,
            submission_id=sub.submission_id,
            external_ref=sub.external_ref,
            status=parsed.adjudication_status,
            raw_payload={"source": "remittance", **parsed.raw_payload},
            timestamp_utc=parsed.timestamp_utc or _now(),
        )

    rem = remittance_repo.upsert_remittance(db, parsed)

    # Outcome synchronization from remittance adjudication.
    if parsed.adjudication_status in {"approved", "denied"} and parsed.case_id:
        outcome_repo.record_outcome(
            db,
            case_id=parsed.case_id,
            outcome=parsed.adjudication_status,
            payer_id=None,
            procedure_code=None,
            diagnosis_code=None,
            reason_codes=parsed.denial_codes,
            turnaround_days=None,
            requested_addenda=[],
            amount=parsed.paid_amount,
            timestamp_utc=parsed.timestamp_utc or _now(),
        )

    audit_repo.write_event(
        db,
        event_type="remittance_ingest",
        actor_id=auth.subject,
        resource_type="remittance",
        resource_id=parsed.remittance_id,
        outcome=parsed.adjudication_status,
        details={
            "case_id": parsed.case_id,
            "submission_id": parsed.submission_id,
            "source_format": parsed.source_format,
        },
        timestamp_utc=parsed.timestamp_utc or _now(),
        trace_id=get_trace_id(request),
    )

    return {
        "remittance_id": parsed.remittance_id,
        "case_id": parsed.case_id,
        "submission_id": parsed.submission_id,
        "status": parsed.adjudication_status,
        "paid_amount": parsed.paid_amount,
    }


@case_router.get("/{case_id}/remittance")
def get_case_remittance(
    case_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("viewer", "reviewer", "admin", "ops_submitter")),
):
    rows = remittance_repo.list_remittances_by_case(db, case_id)
    return [
        {
            "remittance_id": r.remittance_id,
            "case_id": r.case_id,
            "submission_id": r.submission_id,
            "external_ref": r.external_ref,
            "adjudication_status": r.adjudication_status,
            "paid_amount": r.paid_amount,
            "allowed_amount": r.allowed_amount,
            "denial_codes": r.denial_codes,
            "payer_claim_id": r.payer_claim_id,
            "source_format": r.source_format,
            "timestamp_utc": r.timestamp_utc,
        }
        for r in rows
    ]
