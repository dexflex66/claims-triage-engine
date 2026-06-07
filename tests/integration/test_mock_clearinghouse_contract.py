from connectors.us_278_837 import US278837Connector
from service.mock_clearinghouse import InProcessMockClearinghouse


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


def test_mock_clearinghouse_contract_end_to_end(monkeypatch):
    mock = InProcessMockClearinghouse()
    monkeypatch.setenv("US278_BASE_URL", "http://mock.local")
    monkeypatch.setenv("US278_ENFORCE_CONTRACT", "false")
    monkeypatch.setenv("US278_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "kid-1")
    monkeypatch.setenv("US278_BACKOFF_SECONDS", "0")
    monkeypatch.setattr("connectors.us_278_837.urlopen", mock.urlopen)

    connector = US278837Connector()
    ack = connector.submit(_us_packet("CASE-LIVE-1"), idempotency_key="idem-live-1")
    assert ack.status == "submitted"

    last = None
    for _ in range(5):
        last = connector.poll_status(ack.external_ref)
        if last.status in {"approved", "denied"}:
            break
    assert last is not None
    assert last.status == "approved"

    receipt = connector.fetch_receipt(ack.external_ref)
    assert receipt.artifact_ref.startswith("mock-receipt://")

    submit_calls = [r for r in mock.state.request_log if r["method"] == "POST" and r["path"] == "/api/v1/prior-auth/submit"]
    assert submit_calls, "expected submit call log"
    headers = submit_calls[0]["headers"]
    assert headers.get("x-idempotency-key") == "idem-live-1"
    assert "x-quest-signature" in headers
    assert headers.get("x-quest-key-id") == "kid-1"


def test_mock_clearinghouse_idempotency(monkeypatch):
    mock = InProcessMockClearinghouse()
    monkeypatch.setenv("US278_BASE_URL", "http://mock.local")
    monkeypatch.setenv("US278_ENFORCE_CONTRACT", "false")
    monkeypatch.delenv("US278_HMAC_SECRET", raising=False)
    monkeypatch.setenv("US278_BACKOFF_SECONDS", "0")
    monkeypatch.setattr("connectors.us_278_837.urlopen", mock.urlopen)

    connector = US278837Connector()
    a1 = connector.submit(_us_packet("CASE-LIVE-2"), idempotency_key="idem-live-2")
    a2 = connector.submit(_us_packet("CASE-LIVE-2"), idempotency_key="idem-live-2")

    assert a1.submission_id == a2.submission_id
    assert a1.external_ref == a2.external_ref

    submit_calls = [r for r in mock.state.request_log if r["method"] == "POST" and r["path"] == "/api/v1/prior-auth/submit"]
    assert len(submit_calls) == 2
