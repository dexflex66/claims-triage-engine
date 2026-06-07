from connectors.india_preauth import IndiaPreauthConnector
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


def test_us_connector_contract():
    c = US278837Connector()
    ack = c.submit(_us_packet("C1"), idempotency_key="id1")
    assert ack.status == "submitted"
    st = c.poll_status(ack.external_ref)
    assert st.status in {"acknowledged", "processing", "approved", "denied", "submitted"}
    rec = c.fetch_receipt(ack.external_ref)
    assert rec.external_ref == ack.external_ref


def test_india_connector_contract():
    c = IndiaPreauthConnector()
    ack = c.submit({"case_id": "C2"}, idempotency_key="id2")
    assert ack.status == "submitted"
    st = c.poll_status(ack.external_ref)
    assert st.status in {"acknowledged", "processing", "approved", "denied", "submitted"}
