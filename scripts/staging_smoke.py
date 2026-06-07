"""Single-command staging smoke flow.

Runs: compile -> submit -> status -> remittance ingest -> payment post
using fixture packs and emits summary JSON.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

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


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_smoke(dataset: str, output: Path) -> dict:
    dataset = dataset.lower().strip()
    if dataset not in {"us", "in"}:
        raise ValueError("dataset must be us or in")

    root = Path(__file__).resolve().parent.parent
    fixture_dir = root / "fixtures" / dataset

    compile_req = _load_json(fixture_dir / "compile_request.json")
    remittance_req = _load_json(fixture_dir / "remittance_approved.json")
    payment_req = _load_json(fixture_dir / "payment_post_request.json")

    # Safe defaults for local smoke
    os.environ.setdefault("OIDC_REQUIRE_SIGNATURE", "false")
    os.environ.setdefault("KEY_ROTATION_ENFORCED", "false")
    os.environ.setdefault("MTLS_REQUIRED", "false")
    os.environ.setdefault("IP_ALLOWLIST_ENABLED", "false")

    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = f"sqlite:///{(root / f'payer_proof_claims_smoke_{dataset}.db').as_posix()}"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    token = _jwt(
        {
            "sub": "staging-smoke",
            "roles": ["admin", "reviewer", "ops_submitter", "viewer"],
            "aud": os.environ.get("OIDC_AUDIENCE", "payer-proof-claims"),
            "exp": int(time.time()) + 3600,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    summary: dict = {
        "dataset": dataset,
        "timestamp": int(time.time()),
        "steps": {},
        "ok": False,
    }

    with TestClient(app) as client:
        r1 = client.post("/v1/cases/compile", json=compile_req, headers=headers)
        summary["steps"]["compile"] = {"status_code": r1.status_code, "ok": r1.status_code == 200}
        if r1.status_code != 200:
            summary["error"] = {"step": "compile", "detail": r1.text}
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        case_id = compile_req["case_id"]
        submit_req = {
            "submission_channel": "us_278_837" if dataset == "us" else "india_preauth",
            "idempotency_key": f"smoke-{dataset}-submit-1",
        }
        r2 = client.post(f"/v1/cases/{case_id}/submit", json=submit_req, headers=headers)
        summary["steps"]["submit"] = {"status_code": r2.status_code, "ok": r2.status_code == 200}
        if r2.status_code != 200:
            summary["error"] = {"step": "submit", "detail": r2.text}
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        sub = r2.json()
        r3 = client.get(f"/v1/cases/{case_id}/status", headers=headers)
        summary["steps"]["status"] = {"status_code": r3.status_code, "ok": r3.status_code == 200}
        if r3.status_code != 200:
            summary["error"] = {"step": "status", "detail": r3.text}
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        remittance_req["payload"]["case_id"] = case_id
        remittance_req["payload"]["submission_id"] = sub["submission_id"]
        remittance_req["payload"]["external_ref"] = sub["external_ref"]

        r4 = client.post("/v1/remittance/ingest", json=remittance_req, headers=headers)
        summary["steps"]["remittance_ingest"] = {"status_code": r4.status_code, "ok": r4.status_code == 200}
        if r4.status_code != 200:
            summary["error"] = {"step": "remittance_ingest", "detail": r4.text}
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        r5 = client.post(f"/v1/cases/{case_id}/payment/post", json=payment_req, headers=headers)
        summary["steps"]["payment_post"] = {"status_code": r5.status_code, "ok": r5.status_code == 200}
        if r5.status_code != 200:
            summary["error"] = {"step": "payment_post", "detail": r5.text}
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        payment_out = r5.json()
        summary["ok"] = True
        summary["result"] = {
            "case_id": case_id,
            "submission_id": sub.get("submission_id"),
            "external_ref": sub.get("external_ref"),
            "payment_post_id": payment_out.get("payment_post_id"),
            "payment_status": payment_out.get("status"),
            "payment_amount": payment_out.get("amount"),
            "currency": payment_out.get("currency"),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["us", "in"], default="us")
    parser.add_argument("--output", default="artifacts/staging_smoke_summary.json")
    args = parser.parse_args()

    out_path = Path(args.output)
    summary = run_smoke(args.dataset, out_path)
    print(json.dumps(summary, indent=2))
