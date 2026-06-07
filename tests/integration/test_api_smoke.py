import base64
import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _jwt(payload):
    header = {"alg": "none", "typ": "JWT"}

    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{enc(header)}.{enc(payload)}."


def test_compile_and_submit_flow(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)
    token = _jwt(
        {
            "sub": "tester",
            "roles": ["admin", "reviewer", "ops_submitter", "viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    compile_payload = {
        "case_id": "CASE-100",
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
            {"field": "clinical_indication", "value": "Low back pain", "provenance": "CLINICAL_NOTE_V1"},
        ],
    }
    with TestClient(app) as client:
        r = client.post("/v1/cases/compile", json=compile_payload, headers=headers)
        assert r.status_code == 200, r.text

        submit_payload = {
            "submission_channel": "us_278_837",
            "idempotency_key": "idem-1",
        }
        s = client.post("/v1/cases/CASE-100/submit", json=submit_payload, headers=headers)
        assert s.status_code == 200, s.text
        first = s.json()

        # Idempotency: same case + key should return same logical submission.
        s2 = client.post("/v1/cases/CASE-100/submit", json=submit_payload, headers=headers)
        assert s2.status_code == 200, s2.text
        second = s2.json()
        assert first["submission_id"] == second["submission_id"]


def test_compile_accepts_mapped_provenance_prefix(tmp_path):
    db_path = tmp_path / "test_provenance_alias.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)
    token = _jwt(
        {
            "sub": "tester",
            "roles": ["admin", "reviewer", "ops_submitter", "viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    compile_payload = {
        "case_id": "CASE-ALIAS-100",
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
            {"field": "patient_id", "value": "P1", "provenance": "CMS_SYNPUF_CARRIER_1A"},
            {"field": "diagnosis_code", "value": "M54.5", "provenance": "CMS_SYNPUF_CARRIER_1A"},
            {"field": "procedure_code", "value": "72148", "provenance": "CMS_SYNPUF_CARRIER_1A"},
            {"field": "provider_npi", "value": "1234567890", "provenance": "CMS_SYNPUF_CARRIER_1A"},
            {"field": "clinical_indication", "value": "Low back pain", "provenance": "CMS_SYNPUF_CARRIER_1A"},
        ],
    }

    with TestClient(app) as client:
        r = client.post("/v1/cases/compile", json=compile_payload, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision_kind"] == "COMMIT"
        assert "R_PROVENANCE_LOW" not in body["reasons"]
        assert body["compile_result"]["provenance_score"] >= 0.85
        assert body["compile_result"]["provenance_remapped_count"] == 5
