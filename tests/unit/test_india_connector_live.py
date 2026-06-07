import json
from urllib.error import HTTPError

from connectors.india_preauth import IndiaPreauthConnector


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


def test_india_live_submit_signing_headers(monkeypatch):
    monkeypatch.setenv("IN_PREAUTH_BASE_URL", "https://example.com")
    monkeypatch.setenv("IN_PREAUTH_AUTH_MODE", "hmac")
    monkeypatch.setenv("IN_PREAUTH_HMAC_SECRET", "secret123")
    monkeypatch.setenv("IN_PREAUTH_HMAC_KEY_ID", "k1")

    captured = {}

    def _fake_urlopen(req, timeout):
        captured["headers"] = dict(req.header_items())
        captured["method"] = req.get_method()
        return _Resp({"submission_id": "sub_in_live_1", "external_ref": "inext1", "status": "accepted"})

    monkeypatch.setattr("connectors.india_preauth.urlopen", _fake_urlopen)

    c = IndiaPreauthConnector()
    ack = c.submit({"case_id": "IN-C1", "payer_id": "STAR"}, idempotency_key="idem-in-abc")

    assert ack.submission_id == "sub_in_live_1"
    assert ack.external_ref == "inext1"
    assert ack.status == "acknowledged"
    assert captured["method"] == "POST"
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert "x-quest-signature" in headers
    assert headers.get("x-idempotency-key") == "idem-in-abc"


def test_india_live_retry_then_success(monkeypatch):
    monkeypatch.setenv("IN_PREAUTH_BASE_URL", "https://example.com")
    monkeypatch.setenv("IN_PREAUTH_AUTH_MODE", "hmac")
    monkeypatch.setenv("IN_PREAUTH_HMAC_SECRET", "secret123")
    monkeypatch.setenv("IN_PREAUTH_HMAC_KEY_ID", "k1")
    monkeypatch.setenv("IN_PREAUTH_MAX_RETRIES", "2")
    monkeypatch.setenv("IN_PREAUTH_BACKOFF_SECONDS", "0")

    calls = {"n": 0}

    def _fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPError(req.full_url, 503, "svc unavailable", hdrs=None, fp=None)
        return _Resp({"status": "processing"})

    monkeypatch.setattr("connectors.india_preauth.urlopen", _fake_urlopen)

    c = IndiaPreauthConnector()
    st = c.poll_status("inext-1")
    assert calls["n"] == 2
    assert st.status == "processing"
