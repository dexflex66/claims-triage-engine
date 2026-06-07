"""Approval packet generator with citation integrity checks."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_approval_packet(
    compile_result: Dict[str, Any],
    policy: Any,
    case_id: str,
    payer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build approval packet with policy and chart citations."""
    criteria_met = list(compile_result.get("criteria_met") or [])
    evidence_citations = list(compile_result.get("evidence_citations") or [])

    by_field: Dict[str, List[Dict[str, Any]]] = {}
    for c in evidence_citations:
        f = c.get("field")
        if f:
            by_field.setdefault(f, []).append(c)

    required_names = [f.name for f in policy.required_fields] if hasattr(policy, "required_fields") else []
    sections: List[Dict[str, Any]] = []

    for req in required_names:
        satisfied = req in criteria_met
        cites = by_field.get(req, [])
        clause_ref = f"policy.required.{req}"
        chart_refs = [
            {
                "provenance": c.get("provenance"),
                "page": c.get("page"),
                "line": c.get("line"),
                "value": c.get("value"),
            }
            for c in cites
        ]
        sections.append(
            {
                "criterion": req,
                "policy_clause_ref": clause_ref,
                "satisfied": satisfied,
                "chart_citations": chart_refs,
                "value": cites[0].get("value") if cites else None,
            }
        )

    missing_sections = [s for s in sections if not s["satisfied"]]

    return {
        "case_id": case_id,
        "payer_id": payer_id,
        "decision_kind": compile_result.get("decision_kind", "ABSTAIN"),
        "sections": sections,
        "missing_sections": missing_sections,
        "coverage_score": compile_result.get("coverage_score"),
        "provenance_score": compile_result.get("provenance_score"),
    }


def validate_packet_citations(packet: Dict[str, Any]) -> List[str]:
    """Return list of integrity errors for packet sections."""
    errors: List[str] = []
    for section in packet.get("sections", []):
        criterion = section.get("criterion", "unknown")
        clause = section.get("policy_clause_ref")
        cites = section.get("chart_citations") or []
        satisfied = bool(section.get("satisfied"))

        if not clause:
            errors.append(f"missing_clause:{criterion}")

        if satisfied and not cites:
            errors.append(f"missing_chart_citation:{criterion}")

        for i, c in enumerate(cites):
            if not c.get("provenance"):
                errors.append(f"missing_provenance:{criterion}:{i}")

    return errors
