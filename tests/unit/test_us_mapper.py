import pytest

from connectors.us_278_837_mapper import (
    build_submit_payload,
    parse_receipt_response,
    parse_status_response,
    parse_submit_response,
)
from service.provider_contract import load_contract


def _packet():
    return {
        "case_id": "C1",
        "payer_id": "BCBS",
        "sections": [
            {"criterion": "patient_id", "value": "P1"},
            {"criterion": "diagnosis_code", "value": "M54.5"},
            {"criterion": "procedure_code", "value": "72148"},
            {"criterion": "provider_npi", "value": "1234567890"},
            {"criterion": "clinical_indication", "value": "Low back pain"},
        ],
    }


def test_build_submit_payload_required_fields():
    contract = load_contract("us_278_837")
    out = build_submit_payload(_packet(), contract)
    assert out["member_id"] == "P1"
    assert out["provider_identifier"] == "1234567890"


def test_build_submit_payload_missing_required_raises():
    contract = load_contract("us_278_837")
    p = _packet()
    p["sections"] = [s for s in p["sections"] if s["criterion"] != "diagnosis_code"]
    with pytest.raises(ValueError):
        build_submit_payload(p, contract)


def test_parse_responses():
    contract = load_contract("us_278_837")
    s = parse_submit_response({"submission_id": "s1", "external_ref": "e1", "status": "accepted"}, contract)
    assert s["status"] == "accepted"
    st = parse_status_response({"status": "processing"}, contract)
    assert st["status"] == "processing"
    r = parse_receipt_response({"artifact_ref": "receipt://x"}, contract)
    assert r["artifact_ref"] == "receipt://x"
