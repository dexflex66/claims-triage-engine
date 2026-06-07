"""Remittance/adjudication parsing utilities.

Supports:
- ERA-like JSON payloads (preferred)
- simple line-based 835 text fallback (very limited)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ParsedRemittance:
    remittance_id: str
    case_id: str
    submission_id: str
    external_ref: str
    adjudication_status: str
    paid_amount: float
    allowed_amount: float
    denial_codes: List[str]
    payer_claim_id: str
    source_format: str
    raw_payload: Dict[str, Any]
    timestamp_utc: str


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _norm_status(v: str) -> str:
    s = str(v or "").strip().lower()
    if s in {"approved", "paid", "allow", "allowed"}:
        return "approved"
    if s in {"denied", "deny", "rejected"}:
        return "denied"
    if s in {"partial", "partially_approved", "partially_paid"}:
        return "processing"
    return "processing"


def parse_era_json(payload: Dict[str, Any]) -> ParsedRemittance:
    remittance_id = str(payload.get("remittance_id") or payload.get("era_id") or "")
    case_id = str(payload.get("case_id") or "")
    submission_id = str(payload.get("submission_id") or "")
    external_ref = str(payload.get("external_ref") or payload.get("payer_reference") or "")
    adjudication_status = _norm_status(str(payload.get("adjudication_status") or payload.get("status") or "processing"))
    paid_amount = _to_float(payload.get("paid_amount"), 0.0)
    allowed_amount = _to_float(payload.get("allowed_amount"), 0.0)
    denial_codes = [str(x) for x in (payload.get("denial_codes") or [])]
    payer_claim_id = str(payload.get("payer_claim_id") or "")
    timestamp_utc = str(payload.get("timestamp_utc") or "")

    if not remittance_id:
        raise ValueError("remittance_missing_id")

    return ParsedRemittance(
        remittance_id=remittance_id,
        case_id=case_id,
        submission_id=submission_id,
        external_ref=external_ref,
        adjudication_status=adjudication_status,
        paid_amount=paid_amount,
        allowed_amount=allowed_amount,
        denial_codes=denial_codes,
        payer_claim_id=payer_claim_id,
        source_format="era_json",
        raw_payload=payload,
        timestamp_utc=timestamp_utc,
    )


def parse_835_text(raw_text: str) -> ParsedRemittance:
    """Very minimal parser for pipe-delimited demo records.

    Expected line format:
      REMIT|<remittance_id>|<case_id>|<submission_id>|<external_ref>|<status>|<paid>|<allowed>|<codes_csv>|<payer_claim_id>|<timestamp>
    """
    line = (raw_text or "").strip().splitlines()[0] if raw_text else ""
    parts = line.split("|")
    if len(parts) < 11 or parts[0] != "REMIT":
        raise ValueError("unsupported_835_format")

    return ParsedRemittance(
        remittance_id=parts[1],
        case_id=parts[2],
        submission_id=parts[3],
        external_ref=parts[4],
        adjudication_status=_norm_status(parts[5]),
        paid_amount=_to_float(parts[6], 0.0),
        allowed_amount=_to_float(parts[7], 0.0),
        denial_codes=[c for c in parts[8].split(",") if c],
        payer_claim_id=parts[9],
        source_format="835_text",
        raw_payload={"raw_text": raw_text},
        timestamp_utc=parts[10],
    )
