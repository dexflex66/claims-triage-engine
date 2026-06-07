from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from compiler import compile_case
from local_claims_core import build_approval_packet, validate_packet_citations
from repositories import audit as audit_repo
from repositories import cases as case_repo
from repositories import review as review_repo
from service.deps import get_db, get_trace_id
from service.policy import load_policy_for_country, normalize_evidence_provenance, validate_policy_runtime
from service.schemas import CompileCaseRequest, CompileCaseResponse
from service.security.oidc import AuthContext, require_roles

router = APIRouter(prefix="/v1/cases", tags=["cases"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/compile", response_model=CompileCaseResponse)
def compile_case_endpoint(
    payload: CompileCaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("reviewer", "admin", "ops_submitter")),
):
    policy = load_policy_for_country(payload.country)
    errors = validate_policy_runtime(policy, payload.country, payload.payer_id)
    if errors:
        raise HTTPException(status_code=400, detail={"policy_errors": errors})

    evidence = [e.model_dump() for e in payload.evidence]
    evidence, remapped_count = normalize_evidence_provenance(payload.country, evidence)
    compiled = compile_case(payload.fields, evidence, policy=policy)
    packet = build_approval_packet(compiled, policy, case_id=payload.case_id, payer_id=payload.payer_id)
    if remapped_count:
        compiled["provenance_remapped_count"] = remapped_count

    packet_errors = validate_packet_citations(packet)
    if packet_errors:
        compiled["decision_kind"] = "ABSTAIN"
        compiled.setdefault("triggered_conflicts", []).append("PACKET_CITATION_INTEGRITY")

    decision_code = "APPROVE" if compiled.get("decision_kind") == "COMMIT" else "REVIEW"
    reasons = []
    if compiled.get("missing_evidence"):
        reasons.append("R_MISSING_EVIDENCE")
    if compiled.get("triggered_conflicts"):
        reasons.append("R_CONFLICT_HIGH")
    if compiled.get("provenance_score", 0.0) < getattr(policy, "prov_min", 0.0):
        reasons.append("R_PROVENANCE_LOW")
    if packet_errors:
        reasons.append("R_PACKET_CITATION_INTEGRITY")

    case_repo.upsert_case(db, payload.case_id, payload.country, payload.payer_id, payload.fields)
    case_repo.replace_case_evidence(db, payload.case_id, evidence)
    trace_id = get_trace_id(request)
    case_repo.save_compile_result(
        db,
        case_id=payload.case_id,
        decision_kind=compiled.get("decision_kind", "ABSTAIN"),
        decision_code=decision_code,
        result={**compiled, "approval_packet": packet},
        trace_id=trace_id,
    )
    audit_repo.write_event(
        db,
        event_type="decision",
        actor_id=auth.subject,
        resource_type="case",
        resource_id=payload.case_id,
        outcome=decision_code,
        details={"decision_kind": compiled.get("decision_kind"), "reasons": sorted(set(reasons))},
        timestamp_utc=_now(),
        trace_id=trace_id,
    )

    if compiled.get("decision_kind") != "COMMIT":
        review_repo.enqueue(db, payload.case_id, packet, status="pending")

    return CompileCaseResponse(
        case_id=payload.case_id,
        decision_kind=compiled.get("decision_kind", "ABSTAIN"),
        decision_code=decision_code,
        reasons=sorted(set(reasons)),
        trace_id=trace_id,
        compile_result={**compiled, "approval_packet": packet},
    )
