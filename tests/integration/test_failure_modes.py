import base64
import json
import os
import time

import pytest
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


def _compile_payload(case_id="CASE-FM-1"):
    return {
        "case_id": case_id,
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


def test_invalid_remittance_payload_returns_400(tmp_path):
    db_path = tmp_path / "test_fail_remit.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        bad = {"source_format": "era_json", "payload": {"case_id": "X"}}
        r = client.post("/v1/remittance/ingest", json=bad, headers=_headers())
        assert r.status_code == 400
        assert "invalid_remittance_payload" in r.text


def test_delayed_receipt_is_non_blocking(tmp_path, monkeypatch):
    db_path = tmp_path / "test_fail_receipt.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        assert client.post("/v1/cases/compile", json=_compile_payload("CASE-FM-R"), headers=_headers()).status_code == 200
        s = client.post(
            "/v1/cases/CASE-FM-R/submit",
            json={"submission_channel": "us_278_837", "idempotency_key": "idem-fm-r"},
            headers=_headers(),
        )
        assert s.status_code == 200

        class _Conn:
            def poll_status(self, external_ref):
                from connectors.base import StatusUpdate

                return StatusUpdate(external_ref=external_ref, status="approved", raw_payload={"source": "test"})

            def fetch_receipt(self, external_ref):
                raise RuntimeError("receipt not ready")

        monkeypatch.setattr("service.routes.submission.get_connector", lambda country, payer_id: _Conn())
        st = client.get("/v1/cases/CASE-FM-R/status", headers=_headers())
        assert st.status_code == 200
        body = st.json()
        assert body["status"] == "approved"
        assert "receipt_error" in body["raw_status"]


def test_status_uses_latest_submission_when_multiple_exist(tmp_path):
    db_path = tmp_path / "test_fail_multi_submission.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        assert client.post("/v1/cases/compile", json=_compile_payload("CASE-FM-MULTI"), headers=_headers()).status_code == 200
        s1 = client.post(
            "/v1/cases/CASE-FM-MULTI/submit",
            json={"submission_channel": "us_278_837", "idempotency_key": "idem-fm-multi-1"},
            headers=_headers(),
        )
        s2 = client.post(
            "/v1/cases/CASE-FM-MULTI/submit",
            json={"submission_channel": "us_278_837", "idempotency_key": "idem-fm-multi-2"},
            headers=_headers(),
        )
        assert s1.status_code == 200
        assert s2.status_code == 200
        assert s1.json()["submission_id"] != s2.json()["submission_id"]

        status_resp = client.get("/v1/cases/CASE-FM-MULTI/status", headers=_headers())
        assert status_resp.status_code == 200, status_resp.text
        assert status_resp.json()["submission_id"] == s2.json()["submission_id"]


def test_live_connector_missing_credentials_fails_fast(monkeypatch):
    monkeypatch.setenv("US278_BASE_URL", "https://clearinghouse.example")
    monkeypatch.setenv("US278_ENFORCE_CONTRACT", "true")
    monkeypatch.setenv("US278_AUTH_MODE", "bearer_hmac")
    monkeypatch.delenv("US278_API_TOKEN", raising=False)
    monkeypatch.delenv("US278_HMAC_SECRET", raising=False)
    monkeypatch.delenv("US278_HMAC_KEY_ID", raising=False)

    from service.provider_contract import ProviderContractError

    with pytest.raises(ProviderContractError):
        from connectors.us_278_837 import US278837Connector

        US278837Connector()
