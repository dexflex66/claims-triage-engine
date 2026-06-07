"""Shadow replay runner for historical claim data (no external spend).

Runs local API workflow with mock connectors:
compile -> optional review approve -> submit -> status -> optional outcome post.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{enc(header)}.{enc(payload)}."


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return {}
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("expected object-like value")


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    raise ValueError("expected array-like value")


def _normalize_outcome(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"approved", "approve", "paid", "pass"}:
        return "approved"
    if s in {"denied", "deny", "reject", "rejected", "fail"}:
        return "denied"
    return ""


def _default_evidence(fields: Dict[str, Any], provenance: str) -> List[Dict[str, Any]]:
    return [{"field": k, "value": v, "provenance": provenance} for k, v in fields.items()]


def _load_records(path: Path) -> Iterable[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
        return

    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            for item in payload:
                yield item
            return
        if isinstance(payload, dict):
            yield payload
            return
        raise ValueError("JSON input must be object or array")

    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row
        return

    raise ValueError(f"unsupported input extension: {suffix}")


def _build_compile_payload(
    raw: Dict[str, Any],
    default_country: str,
    default_payer_id: str,
    default_provenance: str,
    run_id: str,
    idx: int,
) -> Dict[str, Any]:
    if "compile_request" in raw:
        req = _as_dict(raw["compile_request"])
        fields = _as_dict(req.get("fields"))
        evidence = _as_list(req.get("evidence")) or _default_evidence(fields, default_provenance)
        return {
            "case_id": str(req.get("case_id") or f"shadow-{run_id}-{idx:06d}"),
            "country": str(req.get("country") or default_country),
            "payer_id": str(req.get("payer_id") or default_payer_id),
            "fields": fields,
            "evidence": evidence,
        }

    fields = _as_dict(raw.get("fields"))
    if not fields:
        fields = {
            k[6:]: v
            for k, v in raw.items()
            if isinstance(k, str) and k.startswith("field_") and v not in {"", None}
        }
    evidence = _as_list(raw.get("evidence")) or _default_evidence(fields, default_provenance)
    return {
        "case_id": str(raw.get("case_id") or f"shadow-{run_id}-{idx:06d}"),
        "country": str(raw.get("country") or default_country),
        "payer_id": str(raw.get("payer_id") or default_payer_id),
        "fields": fields,
        "evidence": evidence,
    }


def _submission_channel(country: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return "india_preauth" if str(country).strip().upper() == "IN" else "us_278_837"


def run_shadow_replay(
    input_path: Path,
    output_csv: Path,
    output_summary: Path,
    default_country: str,
    default_payer_id: str,
    default_provenance: str,
    auto_approve_review: bool,
    max_cases: int,
) -> Dict[str, Any]:
    # Safe no-spend defaults
    os.environ.setdefault("OIDC_REQUIRE_SIGNATURE", "false")
    os.environ.setdefault("KEY_ROTATION_ENFORCED", "false")
    os.environ.setdefault("MTLS_REQUIRED", "false")
    os.environ.setdefault("IP_ALLOWLIST_ENABLED", "false")
    os.environ.setdefault("US278_BASE_URL", "")

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    run_id = str(int(time.time()))
    token = _jwt(
        {
            "sub": "shadow-replay",
            "roles": ["admin", "reviewer", "ops_submitter", "viewer"],
            "aud": os.environ.get("OIDC_AUDIENCE", "payer-proof-claims"),
            "exp": int(time.time()) + 3600,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    rows: List[Dict[str, Any]] = []
    with TestClient(app) as client:
        for idx, raw in enumerate(_load_records(input_path), start=1):
            if max_cases > 0 and idx > max_cases:
                break

            compile_req = _build_compile_payload(
                raw=raw,
                default_country=default_country,
                default_payer_id=default_payer_id,
                default_provenance=default_provenance,
                run_id=run_id,
                idx=idx,
            )
            expected_outcome = _normalize_outcome(raw.get("expected_outcome") or raw.get("outcome"))
            submit_channel = _submission_channel(compile_req["country"], raw.get("submission_channel"))
            row_idempotency = str(raw.get("idempotency_key") or f"shadow-{run_id}-{idx:06d}")

            row: Dict[str, Any] = {
                "idx": idx,
                "case_id": compile_req["case_id"],
                "country": compile_req["country"],
                "payer_id": compile_req["payer_id"],
                "expected_outcome": expected_outcome,
                "compile_http": 0,
                "decision_kind": "",
                "decision_code": "",
                "review_http": 0,
                "submit_http": 0,
                "submission_status": "",
                "status_http": 0,
                "status_value": "",
                "outcome_http": 0,
                "pipeline_ok": False,
                "error": "",
            }

            r1 = client.post("/v1/cases/compile", json=compile_req, headers=headers)
            row["compile_http"] = r1.status_code
            if r1.status_code != 200:
                row["error"] = f"compile:{r1.text}"
                rows.append(row)
                continue

            compile_resp = r1.json()
            row["decision_kind"] = compile_resp.get("decision_kind", "")
            row["decision_code"] = compile_resp.get("decision_code", "")

            if row["decision_kind"] != "COMMIT" and auto_approve_review:
                r_review = client.post(
                    f"/v1/cases/{compile_req['case_id']}/review/approve",
                    json={"reviewer_note": "shadow replay auto-approve", "timestamp_utc": ""},
                    headers=headers,
                )
                row["review_http"] = r_review.status_code
                if r_review.status_code != 200:
                    row["error"] = f"review:{r_review.text}"
                    rows.append(row)
                    continue

            r2 = client.post(
                f"/v1/cases/{compile_req['case_id']}/submit",
                json={"submission_channel": submit_channel, "idempotency_key": row_idempotency},
                headers=headers,
            )
            row["submit_http"] = r2.status_code
            if r2.status_code != 200:
                row["error"] = f"submit:{r2.text}"
                rows.append(row)
                continue

            submit_resp = r2.json()
            row["submission_status"] = submit_resp.get("status", "")

            r3 = client.get(f"/v1/cases/{compile_req['case_id']}/status", headers=headers)
            row["status_http"] = r3.status_code
            if r3.status_code != 200:
                row["error"] = f"status:{r3.text}"
                rows.append(row)
                continue
            status_resp = r3.json()
            row["status_value"] = status_resp.get("status", "")

            if expected_outcome:
                r4 = client.post(
                    f"/v1/cases/{compile_req['case_id']}/outcome",
                    json={"outcome": expected_outcome, "reason_codes": []},
                    headers=headers,
                )
                row["outcome_http"] = r4.status_code
                if r4.status_code != 200:
                    row["error"] = f"outcome:{r4.text}"
                    rows.append(row)
                    continue

            row["pipeline_ok"] = True
            rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "idx",
        "case_id",
        "country",
        "payer_id",
        "expected_outcome",
        "compile_http",
        "decision_kind",
        "decision_code",
        "review_http",
        "submit_http",
        "submission_status",
        "status_http",
        "status_value",
        "outcome_http",
        "pipeline_ok",
        "error",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    ok = sum(1 for r in rows if r["pipeline_ok"])
    commits = sum(1 for r in rows if r["decision_kind"] == "COMMIT")
    reviews = total - commits
    expected_labeled = [r for r in rows if r["expected_outcome"] in {"approved", "denied"}]

    # Approval classifier view for shadow comparison:
    # pred positive = auto-approve commit, actual positive = approved.
    tp = fp = tn = fn = 0
    for r in expected_labeled:
        pred_pos = r["decision_code"] == "APPROVE"
        actual_pos = r["expected_outcome"] == "approved"
        if pred_pos and actual_pos:
            tp += 1
        elif pred_pos and not actual_pos:
            fp += 1
        elif (not pred_pos) and actual_pos:
            fn += 1
        else:
            tn += 1

    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0

    summary = {
        "run_id": run_id,
        "input_path": str(input_path),
        "output_csv": str(output_csv),
        "rows_total": total,
        "rows_pipeline_ok": ok,
        "pipeline_success_rate": (ok / total) if total else 0.0,
        "decision_counts": {"commit": commits, "review_or_abstain": reviews},
        "approval_backtest": {
            "labeled_rows": len(expected_labeled),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": precision,
            "recall": recall,
        },
    }
    output_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to CSV/JSON/JSONL replay records")
    parser.add_argument("--output-csv", default="artifacts/shadow_replay_rows.csv")
    parser.add_argument("--output-summary", default="artifacts/shadow_replay_summary.json")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--default-country", default="US")
    parser.add_argument("--default-payer-id", default="BCBS")
    parser.add_argument("--default-provenance", default="HISTORICAL_REPLAY")
    parser.add_argument("--max-cases", type=int, default=0, help="0 means no limit")
    parser.add_argument(
        "--no-auto-approve-review",
        action="store_true",
        help="Do not auto-approve REVIEW/ABSTAIN cases before submit",
    )
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    elif not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'payer_proof_claims_shadow.db').as_posix()}"

    summary_payload = run_shadow_replay(
        input_path=Path(args.input),
        output_csv=Path(args.output_csv),
        output_summary=Path(args.output_summary),
        default_country=args.default_country,
        default_payer_id=args.default_payer_id,
        default_provenance=args.default_provenance,
        auto_approve_review=not args.no_auto_approve_review,
        max_cases=args.max_cases,
    )
    print(json.dumps(summary_payload, indent=2))
