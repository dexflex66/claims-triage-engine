"""
Missing-evidence engine: consumes compiler output and produces structured gap list
with suggested sources and which clinician can add what.
"""
from __future__ import annotations

from typing import Any, Dict, List


def build_missing_evidence_report(compile_result: Dict[str, Any], policy: Any) -> Dict[str, Any]:
    """
    From compile_case() output and policy, build missing-evidence report with
    suggested_sources and assignable_actor per missing field.
    """
    missing = list(compile_result.get("missing_evidence") or [])
    evidence_sources_by_field = getattr(policy, "evidence_sources_by_field", None) or {}
    actor_hints = {
        "patient_id": "front_desk",
        "diagnosis_code": "clinician",
        "procedure_code": "clinician",
        "provider_npi": "front_desk",
        "provider_id": "front_desk",
        "clinical_indication": "clinician",
    }

    gaps = []
    for field in missing:
        suggested = list(evidence_sources_by_field.get(field, []))
        gaps.append({
            "field": field,
            "suggested_sources": suggested,
            "assignable_actor": actor_hints.get(field, "clinician"),
        })

    return {
        "missing_fields": missing,
        "gaps": gaps,
        "recommended_next_actor": compile_result.get("recommended_next_actor"),
    }
