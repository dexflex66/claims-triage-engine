"""Convert public/synthetic claims CSV into shadow replay JSONL format.

Output schema per line:
{
  "compile_request": {...},
  "expected_outcome": "approved" | "denied"   # optional
}
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


APPROVED_SYNONYMS = {"approved", "approve", "paid", "pass", "accepted", "success"}
DENIED_SYNONYMS = {"denied", "deny", "rejected", "reject", "fail", "declined"}


@dataclass
class ColumnMap:
    patient: Optional[str]
    diagnosis: Optional[str]
    procedure: Optional[str]
    provider: Optional[str]
    payer: Optional[str]
    clinical: Optional[str]
    outcome: Optional[str]
    paid_amount: Optional[str]


def _candidate_lists(preset: str) -> Dict[str, list[str]]:
    synthea = {
        "patient": ["PATIENT", "PATIENTID", "Id", "ID"],
        "diagnosis": ["DIAGNOSIS1", "DIAGNOSISCODE", "REASONCODE", "diagnosis_code"],
        "procedure": ["PROCEDURE1", "PROCEDURECODE", "CPT", "HCPCS_CODE", "procedure_code"],
        "provider": ["CLINICIAN", "PROVIDER", "ORGANIZATION", "NPI", "provider_npi", "provider_id"],
        "payer": ["PAYER", "PAYERID", "INSURANCE", "payer_id"],
        "clinical": ["DESCRIPTION", "REASONDESCRIPTION", "NOTES", "CLINICAL_INDICATION", "clinical_indication"],
        "outcome": ["OUTCOME", "STATUS", "DECISION", "CLAIM_STATUS"],
        "paid_amount": ["PAID_AMOUNT", "CLAIM_PAID", "CLM_PMT_AMT", "amount_paid"],
    }
    cms = {
        "patient": ["DESYNPUF_ID", "BENE_ID", "PATIENT_ID"],
        "diagnosis": ["ICD_DGNS_CD1", "PRNCPAL_DGNS_CD", "DGNS_1_CD", "DIAGNOSIS_CODE"],
        "procedure": ["HCPCS_CD", "CPT_CD", "PRCDR_CD1", "LINE_HCPCS_CD", "PROCEDURE_CODE"],
        "provider": ["PRVDR_NUM", "AT_PHYSN_NPI", "OP_PHYSN_NPI", "NPI", "PROVIDER_ID"],
        "payer": ["PAYER_ID", "PAYER"],
        "clinical": ["CLINICAL_INDICATION", "DIAGNOSIS_DESC", "DESCRIPTION"],
        "outcome": ["CLM_MDCR_NON_PMT_RSN_CD", "CLAIM_STATUS", "OUTCOME", "STATUS"],
        "paid_amount": ["CLM_PMT_AMT", "NCH_CLM_PRVDR_PMT_AMT", "PAID_AMOUNT"],
    }
    if preset == "synthea":
        return synthea
    if preset == "cms":
        return cms

    # auto/generic: prefer broad union
    merged: Dict[str, list[str]] = {}
    for k in synthea:
        seen = []
        for name in synthea[k] + cms[k]:
            if name not in seen:
                seen.append(name)
        merged[k] = seen
    return merged


def _lookup(headers: Iterable[str], explicit: str, candidates: list[str]) -> Optional[str]:
    header_list = list(headers)
    lower_map = {h.lower(): h for h in header_list}
    if explicit:
        if explicit in header_list:
            return explicit
        if explicit.lower() in lower_map:
            return lower_map[explicit.lower()]
        return None
    for c in candidates:
        if c in header_list:
            return c
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def detect_columns(
    headers: Iterable[str],
    preset: str,
    patient_col: str = "",
    diagnosis_col: str = "",
    procedure_col: str = "",
    provider_col: str = "",
    payer_col: str = "",
    clinical_col: str = "",
    outcome_col: str = "",
    paid_amount_col: str = "",
) -> ColumnMap:
    cands = _candidate_lists(preset)
    return ColumnMap(
        patient=_lookup(headers, patient_col, cands["patient"]),
        diagnosis=_lookup(headers, diagnosis_col, cands["diagnosis"]),
        procedure=_lookup(headers, procedure_col, cands["procedure"]),
        provider=_lookup(headers, provider_col, cands["provider"]),
        payer=_lookup(headers, payer_col, cands["payer"]),
        clinical=_lookup(headers, clinical_col, cands["clinical"]),
        outcome=_lookup(headers, outcome_col, cands["outcome"]),
        paid_amount=_lookup(headers, paid_amount_col, cands["paid_amount"]),
    )


def _clean(v: object) -> str:
    return str(v or "").strip()


def _fallback(case_idx: int, country: str, key: str) -> str:
    c = country.upper()
    if key == "patient_id":
        return f"{c}-SYN-{case_idx:07d}"
    if key == "diagnosis_code":
        return "M54.5"
    if key == "procedure_code":
        return "72148" if c == "US" else "RAD_MRI_SPINE_L"
    if key == "provider_npi":
        return "1234567890"
    if key == "provider_id":
        return "IN-PROV-0099"
    if key == "clinical_indication":
        return "Radiology prior authorization requested"
    return ""


def _expected_outcome(raw: dict, colmap: ColumnMap) -> str:
    if colmap.outcome:
        v = _clean(raw.get(colmap.outcome)).lower()
        if v in APPROVED_SYNONYMS:
            return "approved"
        if v in DENIED_SYNONYMS:
            return "denied"
    if colmap.paid_amount:
        try:
            return "approved" if float(_clean(raw.get(colmap.paid_amount)) or "0") > 0 else "denied"
        except Exception:
            return ""
    return ""


def convert_csv_to_shadow_jsonl(
    *,
    input_csv: Path,
    output_jsonl: Path,
    preset: str,
    country: str,
    default_payer_id: str,
    case_prefix: str,
    provenance: str,
    max_rows: int,
    allow_fallbacks: bool,
    patient_col: str = "",
    diagnosis_col: str = "",
    procedure_col: str = "",
    provider_col: str = "",
    payer_col: str = "",
    clinical_col: str = "",
    outcome_col: str = "",
    paid_amount_col: str = "",
) -> dict:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")
    country = country.upper().strip()
    if country not in {"US", "IN"}:
        raise ValueError("country must be US or IN")

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0
    skipped = 0
    colmap: Optional[ColumnMap] = None

    provider_key = "provider_npi" if country == "US" else "provider_id"

    with input_csv.open("r", encoding="utf-8", newline="") as fin, output_jsonl.open(
        "w", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        if reader.fieldnames is None:
            raise ValueError("CSV appears to have no header row")

        colmap = detect_columns(
            reader.fieldnames,
            preset=preset,
            patient_col=patient_col,
            diagnosis_col=diagnosis_col,
            procedure_col=procedure_col,
            provider_col=provider_col,
            payer_col=payer_col,
            clinical_col=clinical_col,
            outcome_col=outcome_col,
            paid_amount_col=paid_amount_col,
        )

        for idx, row in enumerate(reader, start=1):
            total += 1
            if max_rows > 0 and written >= max_rows:
                break

            patient = _clean(row.get(colmap.patient)) if colmap.patient else ""
            diagnosis = _clean(row.get(colmap.diagnosis)) if colmap.diagnosis else ""
            procedure = _clean(row.get(colmap.procedure)) if colmap.procedure else ""
            provider = _clean(row.get(colmap.provider)) if colmap.provider else ""
            payer = _clean(row.get(colmap.payer)) if colmap.payer else ""
            clinical = _clean(row.get(colmap.clinical)) if colmap.clinical else ""
            if not clinical and diagnosis:
                clinical = f"Clinical indication inferred from diagnosis {diagnosis}"

            if allow_fallbacks:
                if not patient:
                    patient = _fallback(idx, country, "patient_id")
                if not diagnosis:
                    diagnosis = _fallback(idx, country, "diagnosis_code")
                if not procedure:
                    procedure = _fallback(idx, country, "procedure_code")
                if not provider:
                    provider = _fallback(idx, country, provider_key)
                if not clinical:
                    clinical = _fallback(idx, country, "clinical_indication")

            required = [patient, diagnosis, procedure, provider, clinical]
            if any(not v for v in required):
                skipped += 1
                continue

            case_id = f"{case_prefix}-{country}-{idx:07d}"
            payer_id = payer or default_payer_id
            fields = {
                "patient_id": patient,
                "diagnosis_code": diagnosis,
                "procedure_code": procedure,
                provider_key: provider,
                "clinical_indication": clinical,
            }
            evidence = [
                {"field": k, "value": v, "provenance": provenance}
                for k, v in fields.items()
            ]
            record: Dict[str, object] = {
                "compile_request": {
                    "case_id": case_id,
                    "country": country,
                    "payer_id": payer_id,
                    "fields": fields,
                    "evidence": evidence,
                }
            }
            eo = _expected_outcome(row, colmap)
            if eo:
                record["expected_outcome"] = eo
            fout.write(json.dumps(record, ensure_ascii=True) + "\n")
            written += 1

    return {
        "ok": True,
        "input_csv": str(input_csv),
        "output_jsonl": str(output_jsonl),
        "preset": preset,
        "country": country,
        "column_map": (colmap.__dict__ if colmap else {}),
        "rows_total": total,
        "rows_written": written,
        "rows_skipped": skipped,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument("--preset", choices=["auto", "synthea", "cms"], default="auto")
    parser.add_argument("--country", choices=["US", "IN"], default="US")
    parser.add_argument("--default-payer-id", default="BCBS")
    parser.add_argument("--case-prefix", default="PUBLIC")
    parser.add_argument("--provenance", default="CLINICAL_NOTE_V1")
    parser.add_argument("--max-rows", type=int, default=0, help="0 means all rows")
    parser.add_argument(
        "--no-fallbacks",
        action="store_true",
        help="Skip rows missing required fields instead of auto-filling placeholders",
    )
    parser.add_argument("--patient-col", default="")
    parser.add_argument("--diagnosis-col", default="")
    parser.add_argument("--procedure-col", default="")
    parser.add_argument("--provider-col", default="")
    parser.add_argument("--payer-col", default="")
    parser.add_argument("--clinical-col", default="")
    parser.add_argument("--outcome-col", default="")
    parser.add_argument("--paid-amount-col", default="")
    args = parser.parse_args()

    summary = convert_csv_to_shadow_jsonl(
        input_csv=Path(args.input),
        output_jsonl=Path(args.output),
        preset=args.preset,
        country=args.country,
        default_payer_id=args.default_payer_id,
        case_prefix=args.case_prefix,
        provenance=args.provenance,
        max_rows=args.max_rows,
        allow_fallbacks=not args.no_fallbacks,
        patient_col=args.patient_col,
        diagnosis_col=args.diagnosis_col,
        procedure_col=args.procedure_col,
        provider_col=args.provider_col,
        payer_col=args.payer_col,
        clinical_col=args.clinical_col,
        outcome_col=args.outcome_col,
        paid_amount_col=args.paid_amount_col,
    )
    print(json.dumps(summary, indent=2))
