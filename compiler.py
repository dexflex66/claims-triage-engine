"""Policy evidence compiler entry point.

Must run before any local 'core' package import so `from core.policy` resolves
against QuEST core.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Resolve QuEST root before importing our core
_QUEST_ROOT = Path(__file__).resolve().parent.parent / "proof_first" / "clean_quest"
_QUEST_ROOT = Path(__import__("os").environ.get("QUEST_ROOT", str(_QUEST_ROOT)))
if str(_QUEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_QUEST_ROOT))

try:
    from core.policy import Policy, load_policy  # noqa: E402
    from core.scoring import conflict_score, coverage_score, provenance_score  # noqa: E402
    from core.conflicts import derive_conflicts as quest_derive_conflicts  # noqa: E402
    QUEST_AVAILABLE = True
except ModuleNotFoundError:
    QUEST_AVAILABLE = False

    class Policy:  # type: ignore[no-redef]
        pass

    def load_policy(*a, **kw):
        raise RuntimeError("QuEST core not available — set QUEST_ROOT env var")

    def coverage_score(*a, **kw):
        raise RuntimeError("QuEST core not available — set QUEST_ROOT env var")

    def conflict_score(*a, **kw):
        raise RuntimeError("QuEST core not available — set QUEST_ROOT env var")

    def provenance_score(*a, **kw):
        raise RuntimeError("QuEST core not available — set QUEST_ROOT env var")

    def quest_derive_conflicts(*a, **kw):
        raise RuntimeError("QuEST core not available — set QUEST_ROOT env var")


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _derive_claims_conflicts(fields, rule_ids):
    """Deterministic claim-specific conflict checks.

    Rules are intentionally strict and rely only on provided fields.
    """
    out = []
    f = fields or {}
    ids = set(rule_ids or [])

    dx = str(f.get("diagnosis_code", "") or "").strip().upper()
    proc = str(f.get("procedure_code", "") or "").strip().upper()

    if "DIAGNOSIS_PROCEDURE_MISMATCH" in ids:
        if dx and proc and dx == proc:
            out.append("DIAGNOSIS_PROCEDURE_MISMATCH")

    if "DUPLICATE_PROCEDURE_DATE" in ids:
        d1 = str(f.get("procedure_date", "") or "").strip()
        d2 = str(f.get("previous_procedure_date", "") or "").strip()
        if d1 and d2 and d1 == d2 and proc:
            out.append("DUPLICATE_PROCEDURE_DATE")

    if "PROVENANCE_CONTRADICTION" in ids:
        # If conflicting values are explicitly provided for the same canonical field,
        # mark contradiction.
        if f.get("diagnosis_code_claim") and f.get("diagnosis_code_note"):
            if str(f.get("diagnosis_code_claim")).strip().upper() != str(f.get("diagnosis_code_note")).strip().upper():
                out.append("PROVENANCE_CONTRADICTION")

    return sorted(set(out))


def _decision_reasons(policy: Policy, cov: float, con: float, prov: float, missing, triggered):
    reasons = []
    if missing:
        reasons.append("R_MISSING_EVIDENCE")
    if triggered or con > policy.con_max:
        reasons.append("R_CONFLICT_HIGH")
    if prov < policy.prov_min:
        reasons.append("R_PROVENANCE_LOW")
    if cov < policy.cov_min:
        reasons.append("R_SCHEMA_INVALID")
    return sorted(set(reasons))


def compile_case(fields, evidence, policy=None, policy_path=None):
    if policy is None and policy_path:
        policy = load_policy(policy_path)
    if policy is None:
        raise ValueError("policy or policy_path required")

    cov, missing = coverage_score(policy, fields)
    rule_ids = [r.id for r in policy.conflict_rules]
    quest_conflicts = quest_derive_conflicts(fields, rule_ids)
    claims_conflicts = _derive_claims_conflicts(fields, rule_ids)
    all_conflicts = list(set(quest_conflicts) | set(claims_conflicts))
    con, triggered = conflict_score(policy, all_conflicts)
    prov = provenance_score(policy, evidence)

    criteria_met = [f.name for f in policy.required_fields if f.name not in missing]
    evidence_citations = [
        {
            "field": ev.get("field"),
            "value": ev.get("value"),
            "provenance": ev.get("provenance"),
            "page": ev.get("page"),
            "line": ev.get("line"),
        }
        for ev in (evidence or [])
        if isinstance(ev, dict) and ev.get("field") and ev.get("provenance")
    ]
    actor_hints = {
        "patient_id": "front_desk",
        "diagnosis_code": "clinician",
        "procedure_code": "clinician",
        "provider_npi": "front_desk",
        "provider_id": "front_desk",
        "clinical_indication": "clinician",
    }
    recommended_next_actor = actor_hints.get(missing[0], "clinician") if missing else None

    decision_kind = "COMMIT" if (cov >= policy.cov_min and con <= policy.con_max and prov >= policy.prov_min) else "ABSTAIN"
    decision_code = "APPROVE" if decision_kind == "COMMIT" else "REVIEW"

    return {
        "criteria_met": criteria_met,
        "evidence_citations": evidence_citations,
        "missing_evidence": missing,
        "recommended_next_actor": recommended_next_actor,
        "coverage_score": cov,
        "conflict_score": con,
        "provenance_score": prov,
        "decision_kind": decision_kind,
        "decision_code": decision_code,
        "reasons": _decision_reasons(policy, cov, con, prov, missing, triggered),
        "triggered_conflicts": triggered,
    }
