"""Run live UAT flow against deployed API using real credentials."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _request_json(base_url: str, method: str, path: str, token: str, payload: dict | None) -> tuple[int, dict | str]:
    url = base_url.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url=url, data=body, method=method.upper())
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
    try:
        return status, json.loads(raw) if raw else {}
    except Exception:
        return status, raw


def run_uat(base_url: str, token: str, dataset: str, out_path: Path) -> dict:
    fixture_dir = ROOT / "fixtures" / dataset
    compile_req = _load_json(fixture_dir / "compile_request.json")
    remittance_req = _load_json(fixture_dir / "remittance_approved.json")
    payment_req = _load_json(fixture_dir / "payment_post_request.json")
    channel = "us_278_837" if dataset == "us" else "india_preauth"
    idem = f"uat-{dataset}-{int(time.time())}"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = {"dataset": dataset, "base_url": base_url, "steps": {}, "ok": False}
    sc, body = _request_json(base_url, "POST", "/v1/cases/compile", token, compile_req)
    report["steps"]["compile"] = {"status_code": sc}
    if sc != 200:
        report["error"] = {"step": "compile", "body": body}
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    case_id = compile_req["case_id"]
    sc, submit = _request_json(
        base_url,
        "POST",
        f"/v1/cases/{case_id}/submit",
        token,
        {"submission_channel": channel, "idempotency_key": idem},
    )
    report["steps"]["submit"] = {"status_code": sc}
    if sc != 200:
        report["error"] = {"step": "submit", "body": submit}
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    sc, status_body = _request_json(base_url, "GET", f"/v1/cases/{case_id}/status", token, None)
    report["steps"]["status"] = {"status_code": sc}
    if sc != 200:
        report["error"] = {"step": "status", "body": status_body}
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    remittance_req["payload"]["case_id"] = case_id
    remittance_req["payload"]["submission_id"] = submit.get("submission_id", "")
    remittance_req["payload"]["external_ref"] = submit.get("external_ref", "")
    sc, rem_body = _request_json(base_url, "POST", "/v1/remittance/ingest", token, remittance_req)
    report["steps"]["remittance_ingest"] = {"status_code": sc}
    if sc != 200:
        report["error"] = {"step": "remittance_ingest", "body": rem_body}
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    sc, payment_body = _request_json(base_url, "POST", f"/v1/cases/{case_id}/payment/post", token, payment_req)
    report["steps"]["payment_post"] = {"status_code": sc}
    if sc != 200:
        report["error"] = {"step": "payment_post", "body": payment_body}
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    report["ok"] = True
    report["result"] = {
        "case_id": case_id,
        "submission_id": submit.get("submission_id"),
        "external_ref": submit.get("external_ref"),
        "payment_post_id": payment_body.get("payment_post_id"),
        "payment_status": payment_body.get("status"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="Deployed API base URL")
    parser.add_argument("--token", required=True, help="Bearer token for UAT actor")
    parser.add_argument("--dataset", choices=["us", "in"], default="us")
    parser.add_argument("--out", default="artifacts/live_uat_report.json")
    args = parser.parse_args()

    report = run_uat(args.base_url, args.token, args.dataset, Path(args.out))
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise SystemExit(2)
