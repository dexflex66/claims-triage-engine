import base64
import json
import os
import time

from fastapi.testclient import TestClient


def _jwt(payload):
    header = {"alg": "none", "typ": "JWT"}

    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{enc(header)}.{enc(payload)}."


def _headers():
    token = _jwt(
        {
            "sub": "tester",
            "roles": ["admin", "reviewer", "ops_submitter", "viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_payment_post_idempotency(tmp_path):
    db_path = tmp_path / "test_payment_idem.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    compile_payload = {
        "case_id": "CASE-IDEMPAY",
        "country": "US",
        "payer_id": "BCBS",
        "fields": {
            "patient_id": "P1",
            "diagnosis_code": "M54.5",
            "procedure_code": "72148",
            "provider_npi": "1234567890",
            "clinical_indication": "Low back pain",
        },
        "evidence": [
            {"field": "patient_id", "value": "P1", "provenance": "CLINICAL_NOTE_V1"},
            {"field": "diagnosis_code", "value": "M54.5", "provenance": "CLINICAL_NOTE_V1"},
            {"field": "procedure_code", "value": "72148", "provenance": "CLINICAL_NOTE_V1"},
            {"field": "provider_npi", "value": "1234567890", "provenance": "CLINICAL_NOTE_V1"},
            {"field": "clinical_indication", "value": "Low back pain", "provenance": "CLINICAL_NOTE_V1"}
        ]
    }

    with TestClient(app) as client:
        assert client.post("/v1/cases/compile", json=compile_payload, headers=_headers()).status_code == 200
        s = client.post(
            "/v1/cases/CASE-IDEMPAY/submit",
            json={"submission_channel": "us_278_837", "idempotency_key": "idem-sub-1"},
            headers=_headers(),
        )
        assert s.status_code == 200
        sub = s.json()

        rem = {
            "source_format": "era_json",
            "payload": {
                "remittance_id": "RMT-IDEMPAY",
                "case_id": "CASE-IDEMPAY",
                "submission_id": sub["submission_id"],
                "external_ref": sub["external_ref"],
                "adjudication_status": "approved",
                "paid_amount": 100.0,
                "allowed_amount": 110.0,
                "denial_codes": [],
                "payer_claim_id": "PC-IDEMPAY",
                "timestamp_utc": "2026-02-17T00:00:00Z"
            }
        }
        assert client.post("/v1/remittance/ingest", json=rem, headers=_headers()).status_code == 200

        req = {"rail": "erp", "idempotency_key": "idem-pay-1", "currency": "USD"}
        p1 = client.post("/v1/cases/CASE-IDEMPAY/payment/post", json=req, headers=_headers())
        p2 = client.post("/v1/cases/CASE-IDEMPAY/payment/post", json=req, headers=_headers())
        assert p1.status_code == 200
        assert p2.status_code == 200
        assert p1.json()["payment_post_id"] == p2.json()["payment_post_id"]
