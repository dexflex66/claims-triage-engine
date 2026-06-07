import json
from urllib.error import HTTPError

import pytest

from connectors.us_278_837 import US278837Connector


def _us_packet(case_id: str):
    return {
        "case_id": case_id,
        "payer_id": "BCBS",
        "sections": [
            {"criterion": "patient_id", "value": "P1"},
            {"criterion": "diagnosis_code", "value": "M54.5"},
            {"criterion": "procedure_code", "value": "72148"},
            {"criterion": "provider_npi", "value": "1234567890"},
            {"criterion": "clinical_indication", "value": "Low back pain"},
        ],
        "coverage_score": 1.0,
        "provenance_score": 0.9,
    }


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_live_submit_signing_headers(monkeypatch):
    monkeypatch.setenv("US278_BASE_URL", "https://example.com")
    monkeypatch.setenv("US278_AUTH_MODE", "hmac")
    monkeypatch.setenv("US278_HMAC_SECRET", "secret123")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "k1")

    captured = {}

    def _fake_urlopen(req, timeout):
        captured["headers"] = dict(req.header_items())
        captured["method"] = req.get_method()
        return _Resp({"submission_id": "sub_live_1", "external_ref": "ext1", "status": "accepted"})

    monkeypatch.setattr("connectors.us_278_837.urlopen", _fake_urlopen)

    c = US278837Connector()
    ack = c.submit(_us_packet("C1"), idempotency_key="idem-abc")

    assert ack.submission_id == "sub_live_1"
    assert ack.external_ref == "ext1"
    assert ack.status == "acknowledged"
    assert captured["method"] == "POST"
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert "x-quest-signature" in headers
    assert headers.get("x-idempotency-key") == "idem-abc"


def test_live_retry_then_success(monkeypatch):
    monkeypatch.setenv("US278_BASE_URL", "https://example.com")
    monkeypatch.setenv("US278_AUTH_MODE", "hmac")
    monkeypatch.setenv("US278_HMAC_SECRET", "secret123")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "k1")
    monkeypatch.setenv("US278_MAX_RETRIES", "2")
    monkeypatch.setenv("US278_BACKOFF_SECONDS", "0")

    calls = {"n": 0}

    def _fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPError(req.full_url, 503, "svc unavailable", hdrs=None, fp=None)
        return _Resp({"status": "processing"})

    monkeypatch.setattr("connectors.us_278_837.urlopen", _fake_urlopen)

    c = US278837Connector()
    st = c.poll_status("ext-1")
    assert calls["n"] == 2
    assert st.status == "processing"
