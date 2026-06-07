"""Request/response mapping for US278 connector."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _section_value(packet: Dict[str, Any], criterion: str) -> Any:
    for sec in packet.get("sections", []) or []:
        if str(sec.get("criterion", "")) == criterion:
            return sec.get("value")
    return None


def _required_fields(contract: Dict[str, Any]) -> List[str]:
    return [str(x) for x in (contract.get("required_submit_fields") or [])]


def build_submit_payload(packet: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    """Map internal approval packet to provider submit payload."""
    mapped = {
        "case_id": packet.get("case_id"),
        "payer_id": packet.get("payer_id"),
        "member_id": _section_value(packet, "patient_id"),
        "diagnosis_code": _section_value(packet, "diagnosis_code"),
        "procedure_code": _section_value(packet, "procedure_code"),
        "provider_identifier": _section_value(packet, "provider_npi") or _section_value(packet, "provider_id"),
        "clinical_summary": _section_value(packet, "clinical_indication"),
        "coverage_score": packet.get("coverage_score"),
        "provenance_score": packet.get("provenance_score"),
        "evidence": packet.get("sections", []),
    }

    missing = [k for k in _required_fields(contract) if mapped.get(k) in (None, "", [])]
    if missing:
        raise ValueError(f"submit_payload_missing_required:{','.join(sorted(missing))}")

    return mapped


def _check_required(resp: Dict[str, Any], required: Iterable[str], label: str) -> None:
    missing = [k for k in required if resp.get(k) in (None, "", [])]
    if missing:
        raise ValueError(f"{label}_missing_required:{','.join(sorted(missing))}")


def parse_submit_response(resp: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    rc = contract.get("response_contract", {}) if isinstance(contract.get("response_contract"), dict) else {}
    required = [str(x) for x in (rc.get("submit_required") or [])]
    _check_required(resp, required, "submit_response")
    return {
        "submission_id": resp.get("submission_id"),
        "external_ref": resp.get("external_ref") or resp.get("reference_id") or resp.get("claim_id"),
        "status": resp.get("status"),
        "raw": resp,
    }


def parse_status_response(resp: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    rc = contract.get("response_contract", {}) if isinstance(contract.get("response_contract"), dict) else {}
    required = [str(x) for x in (rc.get("status_required") or [])]
    _check_required(resp, required, "status_response")
    return {
        "status": resp.get("status"),
        "raw": resp,
    }


def parse_receipt_response(resp: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    rc = contract.get("response_contract", {}) if isinstance(contract.get("response_contract"), dict) else {}
    required = [str(x) for x in (rc.get("receipt_required") or [])]
    _check_required(resp, required, "receipt_response")
    artifact_ref = resp.get("artifact_ref") or resp.get("receipt_url") or resp.get("receipt_id")
    return {
        "artifact_ref": artifact_ref,
        "raw": resp,
    }
